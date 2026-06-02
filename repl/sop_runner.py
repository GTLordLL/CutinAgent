import time
from rich.console import Console, Group
from rich.markdown import Markdown
from rich.panel import Panel
from rich.text import Text
from utils.debug_logger import log_state_snapshot


def run_sop_graph(app, state: dict, console=None) -> tuple[dict, list, str, int, list]:
    """运行 SOP 执行图。

    每完成一个节点即通过 console 实时渲染 Panel，同时收集 node_outputs
    供调用方做汇总。console 为 None 时使用默认 Console。

    Returns:
        (state, node_timings, final_task_status, total_rounds, node_outputs)
        node_outputs: [{"node_name", "duration", "detail_lines", "output"}, ...]
    """
    node_timings = []
    node_outputs = []
    final_task_status = "ONGOING"
    total_rounds = 0
    active_round = 0
    node_start = time.time()
    c = console or Console()

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

                # 实时渲染 Panel（每完成一个节点立即输出，保持原流程行为）
                if node_name == "progress_updater":
                    subtitle = node_name
                else:
                    subtitle = f"{node_name}  [italic]{duration:.2f}s[/italic]"

                # tool_executor: 使用 Markdown 渲染摘要内容
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

    return state, node_timings, final_task_status, total_rounds, node_outputs
