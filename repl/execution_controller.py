"""SOP 执行流程封装。

将 main.py 中 ~150 行的 SOP 执行流程（确认→加载→执行→Compactor→满意度→历史追加→RUN_SUMMARY）
封装为单一入口函数。同时提供 headless 版本供 CLI 模式使用。
"""

import asyncio
import time
from datetime import datetime

from rich.console import Console
from rich.panel import Panel

from utils.sop_loader import load_sop_markdown
from utils.tts_engine import tts_say
from data_nodes.VariableStore import clear as clear_variables, get_all as get_all_variables
from repl.state_manager import reset_sop_state
from repl.sop_runner import run_sop_graph, _iterate_graph_stream
from repl.session_manager import write_run_summary
from repl.llm_runner import fmt_elapsed, run_llm_node_sync


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
    # ── 0. INTERRUPT 恢复检测 ──
    prev_task_status = state.get("task_status", "")
    # 仅当上次以 INTERRUPT 结束且 sop_plan_steps 仍保留进度标记时才恢复
    is_resume = (
        prev_task_status == "INTERRUPT"
        and state.get("sop_plan_steps", "").strip() != ""
    )

    saved_sop_id = state["matched_sop_id"]
    saved_action = state["current_action"]
    saved_long_term = state["long_term_intent"]

    # ── 1. 最终确认（恢复模式下跳过） ──
    if not is_resume:
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
                # 用户提供了补充信息 → 清除 INTERRUPT 状态，作为反馈返回
                state["task_status"] = "ONGOING"
                return {"feedback": confirm}
            else:
                # 用户选择 n → 清除 INTERRUPT 状态
                state["task_status"] = "ONGOING"
                set_status_fn("请重新描述需求")
                new_msg = await wait_confirm_fn()
                return {"feedback": new_msg or ""}

    # ── 2. 加载 SOP（恢复模式下保留已有进度） ──
    if is_resume:
        # 保留 sop_plan_steps（含进度标记）和 task_status="INTERRUPT"
        # _handle_interrupt_resume 会在 Scheduler 启动时标记 INTERRUPT 步骤
        state["user_instruction"] = saved_action
        state["current_action"] = saved_action
        state["long_term_intent"] = saved_long_term
        state["current_round"] = 0
        console.print(Panel(
            f"从中断点恢复执行: [bold]{saved_sop_id}[/bold]\n"
            f"行动: {saved_action}",
            title="恢复", title_align="left", padding=(0, 1),
        ))
    else:
        try:
            sop_md = load_sop_markdown(
                state["matched_sop_id"],
                resources.sop_dir,
                valid_tool_ids,
            )
        except ValueError as e:
            console.print(f"[bold red]SOP 加载失败: {e}[/bold red]")
            tts_say(f"SOP 加载失败: {e}")
            state["current_dialogue"].append({"role": "error", "content": f"SOP load failed: {e}"})
            return state

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
        """后台定时器：每 0.1s 刷新顶部状态栏动画（spinner + dots + 颜色 + 计时）。"""
        try:
            while not sop_stop.is_set():
                elapsed = time.time() - sop_start
                top_status_data["label"] = "SOP 执行中"
                top_status_data["elapsed"] = elapsed
                app.invalidate()
                try:
                    await asyncio.wait_for(sop_stop.wait(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass

    sop_timer_task = asyncio.create_task(_sop_timer())

    # ── 3a. 运行 SOP 图 ──
    try:
        state, node_timings, final_task_status, total_rounds, node_outputs = (
            await loop.run_in_executor(
                None, run_sop_graph, app_graph, state, console
            )
        )
        await asyncio.sleep(0.3)

    except Exception as e:
        sop_stop.set()
        await sop_timer_task
        top_status_data["label"] = ""
        top_status_data["elapsed"] = 0
        app.invalidate()
        console.print(f"[bold red]SOP 执行崩溃: {e}[/bold red]")
        tts_say(f"SOP 执行崩溃: {e}")
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
    tts_say(f"SOP执行完毕。状态: {final_task_status}，耗时 {sop_elapsed:.0f} 秒，共 {total_rounds} 轮。")

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
    top_status_data["label"] = ""
    top_status_data["elapsed"] = 0
    app.invalidate()
    console.print(f"[dim]总耗时 (SOP + TaskCompactor): {fmt_elapsed(total_elapsed)}[/dim]")

    console.print()
    console.print(Panel(
        state["compactor_evaluation"],
        title="执行评价", title_align="left", padding=(0, 1),
    ))
    tts_say(state["compactor_evaluation"])

    # ── 5. 满意度确认 + 状态清理 ──
    set_status_fn("满意吗? (y/n)")
    satisfied = await wait_confirm_fn()

    # 保存写 RUN_SUMMARY 所需字段（reset_sop_state 会清除它们）
    _run_user_query = state.get("current_action", "")

    if satisfied.lower() == 'y':
        if state["compactor_conversation_summary"]:
            state["conversation_history"] += "\n" + state["compactor_conversation_summary"]
        if state["compactor_execution_summary"]:
            state["execution_history"] += "\n" + state["compactor_execution_summary"]
        state["current_dialogue"] = []
        console.print("[dim]总结已记录。可以继续下一个任务了。[/dim]")
        tts_say("总结已记录。可以继续下一个任务了。")
        # FINISH 后清除执行状态，避免干扰后续执行；INTERRUPT 保留状态等待恢复
        if final_task_status == "FINISH":
            state = reset_sop_state(state)
    else:
        console.print("[dim]总结未记录。请告诉我如何调整？[/dim]")
        # 用户拒绝（n）→ 清除全部执行状态，避免残留 INTERRUPT 干扰后续执行
        state = reset_sop_state(state)

    write_run_summary(
        session_dir=session_dir,
        user_query=_run_user_query,
        start_dt=datetime.fromtimestamp(sop_start),
        end_dt=datetime.fromtimestamp(sop_start + sop_elapsed),
        elapsed=sop_elapsed,
        node_timings=node_timings,
        final_task_status=final_task_status,
        total_rounds=total_rounds,
    )

    clear_variables()
    return state


def execute_sop_flow_headless(
    state: dict,
    resources,
    app_graph,
    valid_tool_ids: set,
    task_compactor_fn,
    session_dir: str,
) -> dict:
    """执行完整的 SOP 流程（Headless 模式，无 TUI 依赖）。

    与 execute_sop_flow 的区别：
    - 无确认步骤（调用方已确认）
    - 无 TTS 播报
    - 无 Rich Panel 渲染
    - 无满意度问询（自动记录总结）
    - 无异步定时器（纯同步）

    Returns:
        包含执行结果的 dict，字段见 HeadlessRunResult dataclass。
    """
    import os as _os
    from cli.output_formatter import HeadlessRunResult

    # 设置 headless 环境变量，让工具层（report_generator 等）也能静默
    _os.environ["CUTIN_HEADLESS"] = "1"

    result = HeadlessRunResult()
    t_start = time.time()

    try:
        # ── 1. 加载 SOP ──
        try:
            sop_md = load_sop_markdown(
                state["matched_sop_id"],
                resources.sop_dir,
                valid_tool_ids,
            )
        except ValueError as e:
            result.status = "error"
            result.sop_id = state.get("matched_sop_id", "")
            result.error = f"SOP 加载失败: {e}"
            return result

        saved_sop_id = state["matched_sop_id"]
        saved_action = state.get("current_action", state.get("user_instruction", ""))
        saved_long_term = state.get("long_term_intent", "")

        # INTERRUPT 恢复检测
        prev_task_status = state.get("task_status", "")
        is_resume = (
            prev_task_status == "INTERRUPT"
            and state.get("sop_plan_steps", "").strip() != ""
        )

        if is_resume:
            # 保留 sop_plan_steps（含进度标记）和 task_status="INTERRUPT"
            state["user_instruction"] = saved_action
            state["current_action"] = saved_action
            state["long_term_intent"] = saved_long_term
            state["current_round"] = 0
        else:
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

        # ── 2. 运行 SOP 图 ──
        try:
            state, node_timings, final_task_status, total_rounds, node_outputs = (
                _iterate_graph_stream(app_graph, state, node_callback=None)
            )
        except Exception as e:
            import traceback
            result.status = "error"
            result.sop_id = saved_sop_id
            result.error = f"SOP 执行崩溃: {e}\n{traceback.format_exc()}"
            return result

        sop_elapsed = time.time() - t_start

        # ── 3. TaskCompactor（同步，无定时器）──
        compactor_result, _compactor_elapsed = run_llm_node_sync(
            "TaskCompactor", task_compactor_fn, state
        )
        state.update(compactor_result)

        total_elapsed = time.time() - t_start

        # ── 4. 自动记录总结（headless 无人确认，默认记录）──
        if state.get("compactor_conversation_summary"):
            state["conversation_history"] += "\n" + state["compactor_conversation_summary"]
        if state.get("compactor_execution_summary"):
            state["execution_history"] += "\n" + state["compactor_execution_summary"]
        state["current_dialogue"] = []

        # 保存 RUN_SUMMARY 所需字段（reset_sop_state 会清除）
        _run_user_query = state.get("current_action", "")

        # FINISH 后清除执行状态，避免残留 INTERRUPT 干扰后续执行
        if final_task_status == "FINISH":
            state = reset_sop_state(state)

        # ── 5. 写 RUN_SUMMARY ──
        write_run_summary(
            session_dir=session_dir,
            user_query=_run_user_query,
            start_dt=datetime.fromtimestamp(t_start),
            end_dt=datetime.fromtimestamp(t_start + sop_elapsed),
            elapsed=sop_elapsed,
            node_timings=node_timings,
            final_task_status=final_task_status,
            total_rounds=total_rounds,
        )

        # ── 6. 收集变量后清除 ──
        variables_snapshot = get_all_variables()
        clear_variables()

        # ── 7. 构造结果 ──
        result.status = "success"
        result.sop_id = saved_sop_id
        result.task_status = final_task_status
        result.chat_message = state.get("chat_message", "")
        result.total_rounds = total_rounds
        result.total_duration_s = total_elapsed
        result.node_outputs = node_outputs
        result.compactor_evaluation = state.get("compactor_evaluation", "")
        result.compactor_conversation_summary = state.get("compactor_conversation_summary", "")
        result.compactor_execution_summary = state.get("compactor_execution_summary", "")
        result.variables = variables_snapshot
        result.final_report = state.get("final_report", "")
        result.session_dir = session_dir

        return result

    finally:
        _os.environ.pop("CUTIN_HEADLESS", None)
