import time
from utils.debug_logger import log_state_snapshot


def run_sop_graph(app, state: dict, console=None) -> tuple[dict, list, str, int, list]:
    """运行 SOP 执行图。

    Returns:
        (state, node_timings, final_task_status, total_rounds, node_outputs)
        node_outputs: [{"node_name", "duration", "detail_lines", "output"}, ...]
        调用方可按需渲染 (Rich Panel) 或做其他处理。
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
