import time
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from utils.debug_logger import log_state_snapshot
from utils.cancel_token import check_cancel
from utils.tts_engine import tts_say

# 报告类工具的 conclusion 值 —— 匹配时立即 TTS 播报
_REPORT_CONCLUSIONS = {
    "已生成今日变更日报",
    "已生成 Commit Message",
    "已通过子代理生成总结报告",
}


def _build_detail_lines(node_name: str, output: dict) -> list[str]:
    """构建节点的可读摘要行（纯逻辑，无 I/O）。"""
    detail_lines = []
    if node_name == "sop_execution_scheduler":
        ls = output.get("last_step", "?")
        tc = output.get("current_tool_call", "?")
        ta = output.get("current_tool_args", {})
        ts_out = output.get("task_status", "?")
        detail_lines.append(f"下一步: {ls}")
        detail_lines.append(f"工具: {tc}{ta}  |  状态: {ts_out}")

    elif node_name == "tool_executor":
        ts_out = output.get("tool_status", "")
        tc = output.get("tool_conclusion", "")
        tsm = output.get("tool_summary", "")
        tdv = output.get("tool_detail_var", "")
        detail_lines.append(f"状态: {ts_out}")
        detail_lines.append(f"结论: {tc}")
        if tsm:
            detail_lines.append(f"摘要: {tsm}")
        if tdv:
            detail_lines.append(f"变量: {tdv}")

    elif node_name == "progress_updater":
        plan = output.get("sop_plan_steps", "")
        rnd = output.get("current_round", "?")
        detail_lines.append(f"回合: {rnd}")
        plan_display = str(plan)
        if len(plan_display) > 200:
            detail_lines.append(f"计划: {plan_display[:200]}...")
        else:
            detail_lines.append(f"计划: {plan_display}")

    return detail_lines


def _iterate_graph_stream(app, state: dict, node_callback=None):
    """核心图遍历循环 —— 供 TUI 和 headless 模式共享。

    Args:
        app: LangGraph CompiledGraph
        state: 初始 state dict（原地修改）
        node_callback: 可选回调 (node_name, output, duration, detail_lines) -> None

    Returns:
        (state, node_timings, final_task_status, total_rounds, node_outputs)
    """
    node_timings = []
    node_outputs = []
    final_task_status = "ONGOING"
    total_rounds = 0
    active_round = 0
    node_start = time.time()

    for event in app.stream(state, stream_mode="updates"):
        if event:
            for node_name, output in event.items():
                duration = time.time() - node_start
                node_timings.append((node_name, duration))
                ts = output.get("task_status", "")
                if ts:
                    final_task_status = ts
                cr = output.get("current_round", 0)
                if cr > total_rounds:
                    total_rounds = cr

                # 构建节点输出摘要
                detail_lines = _build_detail_lines(node_name, output)

                # 报告类工具立即 TTS 播报（不等 SOP 执行完毕）
                tsm = output.get("tool_summary", "")
                tc = output.get("tool_conclusion", "")
                if node_name == "tool_executor" and tsm and tc in _REPORT_CONCLUSIONS:
                    tts_say(tsm)

                # 回调：TUI 模式渲染 Panel，headless 模式收集静默
                if node_callback:
                    node_callback(node_name, output, duration, detail_lines)

                node_outputs.append({
                    "node_name": node_name,
                    "duration": duration,
                    "detail_lines": detail_lines,
                    "output": output,
                })

                log_state_snapshot(output, state.get("session_dir", ""), node_name, active_round)

                if node_name == "progress_updater":
                    active_round = output.get("current_round", active_round)

                # 累积 state
                state.update(output)
                node_start = time.time()

            check_cancel()

    return state, node_timings, final_task_status, total_rounds, node_outputs


def run_sop_graph(app, state: dict, console=None) -> tuple[dict, list, str, int, list]:
    """运行 SOP 执行图（TUI 模式）。

    每完成一个节点即通过 console 实时渲染 Rich Panel，同时收集 node_outputs
    供调用方做汇总。console 为 None 时使用默认 Console。

    Returns:
        (state, node_timings, final_task_status, total_rounds, node_outputs)
        node_outputs: [{"node_name", "duration", "detail_lines", "output"}, ...]
    """
    c = console or Console()

    def _render_panel(node_name, output, duration, detail_lines):
        """TUI 回调：每节点完成时渲染 Rich Panel。"""
        if node_name == "progress_updater":
            subtitle = node_name
        else:
            subtitle = f"{node_name}  [italic]{duration:.2f}s[/italic]"

        tool_summary = output.get("tool_summary", "")
        if node_name == "tool_executor" and tool_summary:
            ts_out = output.get("tool_status", "")
            tc = output.get("tool_conclusion", "")
            tdv = output.get("tool_detail_var", "")
            meta = f"状态: {ts_out}\n结论: {tc}"
            if tdv:
                meta += f"\n变量: {tdv}"
            body = Group(
                Text(f"{meta}\n", style=""),
                Markdown(tool_summary),
            )
        else:
            body = Text("\n".join(detail_lines) if detail_lines else "(无输出)", style="")
        c.print(Panel(body, title=subtitle, title_align="left", padding=(0, 1)))

    return _iterate_graph_stream(app, state, node_callback=_render_panel)
