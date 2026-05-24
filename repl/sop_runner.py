import time
from utils.debug_logger import log_state_snapshot


def run_sop_graph(app, state: dict) -> tuple[dict, list, str, int]:
    """运行 SOP 执行图，返回 (state, node_timings, final_task_status, total_rounds)。"""
    node_timings = []
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

                print(f"\n[{node_name}] 耗时: {duration:.2f}s")

                if node_name == "sop_execution_scheduler":
                    ls = output.get("last_step", "?")
                    tc = output.get("current_tool_call", "?")
                    ta = output.get("current_tool_args", {})
                    ts = output.get("task_status", "?")
                    print(f"  下一步: {ls}")
                    print(f"  工具: {tc}{ta}  |  状态: {ts}")

                elif node_name == "tool_executor":
                    ts = output.get("tool_status", "")
                    tc = output.get("tool_conclusion", "")
                    tsm = output.get("tool_summary", "")
                    tdv = output.get("tool_detail_var", "")
                    print(f"  状态: {ts}")
                    print(f"  结论: {tc}")
                    if tsm:
                        print(f"  摘要: {tsm}")
                    if tdv:
                        print(f"  变量: {tdv}")

                elif node_name == "progress_updater":
                    plan = output.get("sop_plan_steps", "")
                    rnd = output.get("current_round", "?")
                    print(f"  回合: {rnd}")
                    plan_display = str(plan)
                    print(f"  更新后计划: {plan_display[:200]}..." if len(plan_display) > 200 else f"  更新后计划: {plan_display}")

                log_state_snapshot(output, state.get("session_dir", ""), node_name, active_round)

                if node_name == "progress_updater":
                    active_round = output.get("current_round", active_round)

                # 累积 state
                state.update(output)
                node_start = time.time()

    return state, node_timings, final_task_status, total_rounds
