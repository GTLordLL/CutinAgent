"""SOP 执行流程封装。

将 main.py 中 ~150 行的 SOP 执行流程（确认→加载→执行→Compactor→满意度→历史追加→RUN_SUMMARY）
封装为单一入口函数。
"""

import asyncio
import time
from datetime import datetime

from rich.console import Console
from rich.panel import Panel

from utils.sop_loader import load_sop_markdown
from data_nodes.VariableStore import clear as clear_variables
from repl.state_manager import reset_sop_state
from repl.sop_runner import run_sop_graph
from repl.session_manager import write_run_summary
from repl.llm_runner import fmt_elapsed


async def execute_sop_flow(
    state: dict,
    resources,
    app_graph,
    valid_tool_ids: set,
    task_compactor_fn,
    session_dir: str,
    top_status_data: dict,
    status_data: dict,
    app,
    console: Console,
    set_status_fn,
    wait_confirm_fn,
) -> dict:
    """执行完整的 SOP 流程：确认 → 加载 → 执行图 → TaskCompactor → 满意度。

    此函数封装了 IS_EXECUTE="true" 后的全部逻辑（原 main.py L437-L563）。
    state 被原地修改并返回。

    Args:
        set_status_fn: 更新底部状态栏的回调，签名 (text: str) -> None
        wait_confirm_fn: 等待用户输入的回调，签名 () -> str
    """
    # ── 1. 最终确认 ──
    console.print(Panel(
        f"[bold]确认执行[/bold]\n"
        f"SOP: {state['matched_sop_id']}\n"
        f"行动: {state['current_action']}\n"
        f"长期计划: {state['long_term_intent']}",
        title="确认", title_align="left", padding=(0, 1),
    ))
    set_status_fn("确认执行? (y=执行 / n=重新规划 / 或输入补充信息)")

    confirm = await wait_confirm_fn()
    if confirm.lower() != 'y':
        if confirm.lower() != 'n':
            # 用户提供了补充信息 → 作为反馈返回给 UserCoordinator
            return {"feedback": confirm}
        else:
            set_status_fn("请重新描述需求")
            new_msg = await wait_confirm_fn()
            return {"feedback": new_msg or ""}

    # ── 2. 加载 SOP ──
    try:
        sop_md = load_sop_markdown(
            state["matched_sop_id"],
            resources.sop_dir,
            valid_tool_ids,
        )
    except ValueError as e:
        console.print(f"[bold red]SOP 加载失败: {e}[/bold red]")
        state["current_dialogue"].append({"role": "error", "content": f"SOP load failed: {e}"})
        return state

    saved_sop_id = state["matched_sop_id"]
    saved_action = state["current_action"]
    saved_long_term = state["long_term_intent"]
    state = reset_sop_state(state)
    state.update({
        "matched_sop_id": saved_sop_id,
        "sop_objective": sop_md.get("objective", ""),
        "sop_plan_steps": sop_md.get("plan_steps", ""),
        "sop_tools_required": sop_md.get("tools_required", ""),
        "sop_exception_handling": sop_md.get("exception_handling", ""),
        "retry_limit": (
            int(sop_md.get("retry_limit", "3").strip())
            if sop_md.get("retry_limit", "3").strip().isdigit()
            else 3
        ),
        "user_instruction": saved_action,
        "current_action": saved_action,
        "long_term_intent": saved_long_term,
        "task_status": "ONGOING",
        "current_round": 0,
    })

    # ── 3. 执行 SOP 图 + TaskCompactor（单一计时器） ──
    set_status_fn(f"执行中: {state['matched_sop_id']}")
    console.print(Panel(
        f"开始执行 SOP: [bold]{state['matched_sop_id']}[/bold]\n"
        f"行动: {state['user_instruction']}",
        title="执行", title_align="left", padding=(0, 1),
    ))

    loop = asyncio.get_running_loop()
    sop_start = time.time()
    sop_stop = asyncio.Event()

    async def _sop_timer():
        """单一计时器：覆盖 SOP 执行 + TaskCompactor 全过程。"""
        try:
            while not sop_stop.is_set():
                elapsed = time.time() - sop_start
                top_status_data["runtime_text"] = f"  SOP: {fmt_elapsed(elapsed)}"
                app.invalidate()
                try:
                    await asyncio.wait_for(sop_stop.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass

    sop_timer_task = asyncio.create_task(_sop_timer())

    # ── 3a. 运行 SOP 图 ──
    try:
        state, node_timings, final_task_status, total_rounds, _node_outputs = (
            await loop.run_in_executor(
                None, run_sop_graph, app_graph, state, console
            )
        )
        await asyncio.sleep(0.3)

    except Exception as e:
        sop_stop.set()
        await sop_timer_task
        top_status_data["runtime_text"] = ""
        app.invalidate()
        console.print(f"[bold red]SOP 执行崩溃: {e}[/bold red]")
        import traceback
        traceback.print_exc()
        state["current_dialogue"].append({"role": "error", "content": f"SOP execution failed: {e}"})
        return state

    sop_elapsed = time.time() - sop_start
    console.print(Panel(
        f"状态: {final_task_status}  |  "
        f"耗时: {sop_elapsed:.2f}s  |  "
        f"轮次: {total_rounds}",
        title="SOP 执行完毕", title_align="left", padding=(0, 1),
    ))
    set_status_fn(f"完成: {state['matched_sop_id']}")

    # ── 3b. TaskCompactor（不单独计时，复用 SOP 计时器）──
    console.print("[dim][TaskCompactor] 评价与总结中...[/dim]")
    compactor_result = await loop.run_in_executor(
        None, task_compactor_fn, state
    )
    await asyncio.sleep(0.3)
    state.update(compactor_result)

    # 停止单一计时器
    total_elapsed = time.time() - sop_start
    sop_stop.set()
    await sop_timer_task
    top_status_data["runtime_text"] = ""
    app.invalidate()
    console.print(f"[dim]总耗时 (SOP + TaskCompactor): {fmt_elapsed(total_elapsed)}[/dim]")

    console.print()
    console.print(Panel(
        state["compactor_evaluation"],
        title="执行评价", title_align="left", padding=(0, 1),
    ))

    # ── 5. 满意度确认 ──
    set_status_fn("满意吗? (y/n)")
    satisfied = await wait_confirm_fn()

    if satisfied.lower() == 'y':
        if state["compactor_conversation_summary"]:
            state["conversation_history"] += "\n" + state["compactor_conversation_summary"]
        if state["compactor_execution_summary"]:
            state["execution_history"] += "\n" + state["compactor_execution_summary"]
        state["current_dialogue"] = []
        console.print("[dim]总结已记录。可以继续下一个任务了。[/dim]")
    else:
        console.print("[dim]总结未记录。请告诉我如何调整？[/dim]")

    write_run_summary(
        session_dir=session_dir,
        user_query=state.get("current_action", ""),
        start_dt=datetime.fromtimestamp(sop_start),
        end_dt=datetime.fromtimestamp(sop_start + sop_elapsed),
        elapsed=sop_elapsed,
        node_timings=node_timings,
        final_task_status=final_task_status,
        total_rounds=total_rounds,
    )

    clear_variables()
    return state
