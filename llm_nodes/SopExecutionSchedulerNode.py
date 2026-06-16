"""SOP Execution Scheduler LLM 节点。

在 SOP 执行循环中每轮运行：根据当前 SOP_PLAN 进度选择下一步工具调用。
Thinker (temp 0.4) + Formatter (temp 0.0) 双阶段。

特殊处理（相比其他 LLM 节点）：
- 前置：INTERRUPT 恢复标记 + 工具过滤（仅允许 SOP 声明的工具）
- 后置：多工具调用并行解析（| 分隔符）
"""

from datetime import date
from rich.console import Console
from parsers.tool_call import _build_tool_signature, _split_parallel_calls
from parsers.sop_plan import _classify_step, StepType, _parse_steps, _reconstruct_plan
from validator.SopExecutionSchedulerValidator import validate_tool_call, validate_scheduler_output
from llm_nodes.thinker_formatter_runner import run_thinker_formatter


# ── 模块级辅助函数 ──

def _handle_interrupt_resume(sop_plan_steps: str) -> str:
    """检测 SOP_PLAN 中未标记的 INTERRUPT 步骤并标记为已完成。

    当上次运行以 INTERRUPT 结束时，用户确认后恢复执行，
    此函数在 Thinker 运行前将 INTERRUPT 步骤标记为完成，
    让 Thinker 自然跳过它继续执行后续步骤。
    """
    steps = _parse_steps(sop_plan_steps)
    if not steps:
        return sop_plan_steps

    for s in steps:
        if _classify_step(s['header']) == StepType.INTERRUPT:
            if "结果:" not in s['header'] and "中断已完成" not in s['header']:
                s['header'] = f"{s['header']} 中断已完成，请继续执行。"
                s['sub_lines'] = []
                return _reconstruct_plan(steps)

    return sop_plan_steps


def _parse_multiple_tool_calls(tool_call_raw: str, valid_tool_ids: set) -> list[dict]:
    """解析 TOOL_CALL 字符串，支持 | 分隔的多个工具调用。
    Returns: [{tool_id, args}, ...]
    """
    calls = []
    for part in _split_parallel_calls(tool_call_raw):
        if not part:
            continue
        is_valid, reason, parsed = validate_tool_call(part, valid_tool_ids)
        if is_valid:
            calls.append(parsed)
    return calls


# ── 节点工厂 ──

def sop_execution_scheduler_node(resources, headless=False):
    """SOP Execution Scheduler 可调用对象工厂。

    Args:
        resources: LLMResources 实例
        headless: True 时禁用终端输出（CLI 模式）
    """
    tools_df = resources.tools_df
    _console = None if headless else Console()

    def node(state: dict) -> dict:
        # ── 前置：INTERRUPT 恢复标记 ──
        sop_plan_steps = state.get("sop_plan_steps", "")
        prev_task_status = state.get("task_status", "")
        if prev_task_status == "INTERRUPT":
            sop_plan_steps = _handle_interrupt_resume(sop_plan_steps)

        # ── 前置：工具过滤（仅允许 SOP 声明的工具）──
        sop_tools_required = state.get("sop_tools_required", "")
        if sop_tools_required:
            required_ids = {t.strip() for t in sop_tools_required.split(",")}
            filtered = tools_df[tools_df["Tool_ID"].isin(required_ids)]
        else:
            filtered = tools_df

        valid_tool_ids = set(filtered["Tool_ID"].tolist())
        tools_lines = []
        for _, row in filtered.iterrows():
            tools_lines.append(_build_tool_signature(row))
        tools_text = "\n".join(tools_lines)

        user_instruction = state.get("user_instruction", "")
        sop_exception_handling = state.get("sop_exception_handling", "")
        last_step = state.get("last_step", "")
        today_str = date.today().isoformat()

        def build_input(s):
            return (
                f"TODAY: {today_str}\n\n"
                f"USER_INSTRUCTION: {user_instruction}\n\n"
                f"SOP_PLAN:\n{sop_plan_steps}\n\n"
                f"EXCEPTION_HANDLING:\n{sop_exception_handling}\n\n"
                f"LAST_STEP: {last_step}\n\n"
                f"AVAILABLE_TOOLS:\n{tools_text}\n"
            )

        def map_result(parsed, thinker_tokens, **ctx):
            tool_call_raw = parsed.get("tool_call", "")
            task_status = parsed.get("task_status", "ONGOING")
            v_tool_ids = ctx.get("valid_tool_ids", set())

            tool_id = ""
            tool_args = {}
            tool_calls_list = []

            if tool_call_raw != "None" and task_status == "ONGOING":
                tool_calls_list = _parse_multiple_tool_calls(tool_call_raw, v_tool_ids)
                if tool_calls_list:
                    tool_id = tool_calls_list[0]["tool_id"]
                    tool_args = tool_calls_list[0]["args"]

            return {
                "current_tool_call": tool_id,
                "current_tool_call_raw": tool_call_raw or "",
                "current_tool_args": tool_args,
                "current_tool_calls": tool_calls_list,
                "last_step": parsed.get("next_step", ""),
                "task_status": task_status,
            }

        return run_thinker_formatter(
            state=state,
            resources=resources,
            thinker_llm_key="sop_execution_scheduler_thinker",
            formatter_llm_key="all_formatter",
            thinker_prompt_key="sop_execution_scheduler_thinker",
            formatter_prompt_key="sop_execution_scheduler_formatter",
            node_name="SopExecutionScheduler",
            build_thinker_input=build_input,
            validate_output=validate_scheduler_output,
            map_result=map_result,
            fallback_result={
                "next_step": "",
                "tool_call": "",
                "task_status": "FAILED",
            },
            thinker_label="Scheduler Thinker",
            formatter_label="Scheduler Formatter",
            console=_console,
            headless=headless,
            valid_tool_ids=valid_tool_ids,
        )

    return node
