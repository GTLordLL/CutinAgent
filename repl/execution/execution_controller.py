"""SOP 执行流程封装。

将 main.py 中 ~150 行的 SOP 执行流程（确认→加载→执行→Compactor→满意度→历史追加→RUN_SUMMARY）
封装为单一入口函数。同时提供 headless 版本供 CLI 模式使用。

共享辅助函数已提取至 repl/execution_helpers.py。
"""

import asyncio
import time

from rich.console import Console
from rich.panel import Panel

from utils.tts_engine import tts_say
from utils.cancel_token import CancellationError, check_cancel
from data_nodes.VariableStore import clear as clear_variables, get_all as get_all_variables
from repl.state.state_manager import reset_sop_state
from repl.execution.sop_runner import run_sop_graph, _iterate_graph_stream
from repl.execution.llm_runner import fmt_elapsed, run_llm_node_sync
from repl.execution.execution_helpers import (
    detect_interrupt_resume,
    resume_state_fields,
    load_sop_and_init_state,
    record_compactor_summaries,
    write_sop_run_summary,
)


# ── Phase 1: 最终确认 ─────────────────────────────────────────────

async def _confirm_execution(
    state: dict,
    is_resume: bool,
    console: Console,
    set_status_fn,
    wait_confirm_fn,
) -> dict | None:
    """向用户确认 SOP 执行。恢复模式下跳过。

    Returns:
        None → 确认执行，继续
        {"feedback": ...} → 用户拒绝或提供反馈，调用方应直接返回该 dict
    """
    if is_resume:
        return None

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
        state["task_status"] = "ONGOING"
        if confirm.lower() != 'n':
            return {"feedback": confirm}
        set_status_fn("请重新描述需求")
        new_msg = await wait_confirm_fn()
        return {"feedback": new_msg or ""}

    return None


# ── Phase 2: 加载 SOP ─────────────────────────────────────────────

def _load_sop_for_execution(
    state: dict,
    resources,
    valid_tool_ids: set,
    is_resume: bool,
    saved_action: str,
    saved_long_term: str,
    console: Console,
) -> dict | None:
    """加载 SOP markdown 并填充 state 字段。

    恢复模式：保留 sop_plan_steps 进度标记。
    全新模式：从 Markdown 文件加载并初始化。

    Returns:
        state → 加载成功
        None → 加载失败，调用方应将错误对话框 state 返回给调用者
    """
    saved_sop_id = state["matched_sop_id"]

    if is_resume:
        resume_state_fields(state, saved_action, saved_long_term)
        console.print(Panel(
            f"从中断点恢复执行: [bold]{saved_sop_id}[/bold]\n"
            f"行动: {saved_action}",
            title="恢复", title_align="left", padding=(0, 1),
        ))
        return state

    try:
        return load_sop_and_init_state(
            state, resources.sop_dir, valid_tool_ids,
            saved_sop_id, saved_action, saved_long_term,
        )
    except ValueError as e:
        console.print(f"[bold red]SOP 加载失败: {e}[/bold red]")
        tts_say(f"SOP 加载失败: {e}")
        state["current_dialogue"].append(
            {"role": "error", "content": f"SOP load failed: {e}"}
        )
        return None


# ── Phase 3: 执行 SOP 图 + TaskCompactor ───────────────────────────

async def _execute_sop_with_timer(
    state: dict,
    app_graph,
    task_compactor_fn,
    console: Console,
    app,
    top_status_data: dict,
    set_status_fn,
) -> tuple:
    """在一个共享计时器下运行 SOP 图 + TaskCompactor。

    计时器驱动顶部状态栏的 spinner / dots / 颜色动画。

    Returns:
        (state, node_timings, final_task_status, total_rounds, sop_start, sop_elapsed)
        其中 node_timings 为 None 表示图执行崩溃（state 已带 error 信息）。
    """
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
        """后台定时器：每 0.1s 刷新顶部状态栏动画。"""
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
    except CancellationError:
        sop_stop.set()
        await sop_timer_task
        top_status_data["label"] = ""
        top_status_data["elapsed"] = 0
        app.invalidate()
        raise
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
        state["current_dialogue"].append(
            {"role": "error", "content": f"SOP execution failed: {e}"}
        )
        return state, None, "", 0, sop_start, 0.0

    sop_elapsed = time.time() - sop_start
    console.print(Panel(
        f"状态: {final_task_status}  |  "
        f"耗时: {sop_elapsed:.2f}s  |  "
        f"轮次: {total_rounds}",
        title="SOP 执行完毕", title_align="left", padding=(0, 1),
    ))
    set_status_fn(f"完成: {state['matched_sop_id']}")
    tts_say(f"SOP执行完毕。状态: {final_task_status}，耗时 {sop_elapsed:.0f} 秒，共 {total_rounds} 轮。")

    check_cancel()

    # ── 3b. TaskCompactor（复用 SOP 计时器）──
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

    return state, node_timings, final_task_status, total_rounds, sop_start, sop_elapsed


# ── Phase 4: 满意度确认 ──────────────────────────────────────────

async def _finalize_execution(
    state: dict,
    console: Console,
    set_status_fn,
    wait_confirm_fn,
    final_task_status: str,
) -> tuple[dict, str]:
    """满意度确认 + 执行状态清理。

    Returns:
        (state, user_query): user_query 供 write_sop_run_summary 使用
    """
    set_status_fn("满意吗? (y/n)")
    satisfied = await wait_confirm_fn()

    _run_user_query = state.get("current_action", "")

    if satisfied.lower() == 'y':
        record_compactor_summaries(state, is_satisfied=True)
        console.print("[dim]总结已记录。可以继续下一个任务了。[/dim]")
        tts_say("总结已记录。可以继续下一个任务了。")
        if final_task_status == "FINISH":
            state = reset_sop_state(state)
    else:
        console.print("[dim]总结未记录。请告诉我如何调整？[/dim]")
        state = reset_sop_state(state)

    return state, _run_user_query


# ── 主入口（精简编排层）──────────────────────────────────────────

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
    """SOP 执行主流程：确认 → 加载 → 执行+Compactor → 满意度 → 摘要。

    Args:
        set_status_fn: 更新底部状态栏的回调，签名 (text: str) -> None
        wait_confirm_fn: 等待用户输入的回调，签名 () -> str
    """
    # ── 0. INTERRUPT 恢复检测 ──
    is_resume = detect_interrupt_resume(state)

    saved_sop_id = state["matched_sop_id"]
    saved_action = state["current_action"]
    saved_long_term = state["long_term_intent"]

    # ── 1. 确认 ──
    feedback = await _confirm_execution(
        state, is_resume, console, set_status_fn, wait_confirm_fn
    )
    if feedback is not None:
        return feedback

    # ── 2. 加载 SOP ──
    loaded = _load_sop_for_execution(
        state, resources, valid_tool_ids, is_resume,
        saved_action, saved_long_term, console,
    )
    if loaded is None:
        return state
    state = loaded

    # ── 3. 执行 SOP 图 + TaskCompactor ──
    state, node_timings, final_task_status, total_rounds, sop_start, sop_elapsed = (
        await _execute_sop_with_timer(
            state, app_graph, task_compactor_fn,
            console, app, top_status_data, set_status_fn,
        )
    )
    if node_timings is None:
        return state  # 图执行崩溃，错误信息已在 state 中

    # ── 4. 满意度 ──
    state, _run_user_query = await _finalize_execution(
        state, console, set_status_fn, wait_confirm_fn, final_task_status
    )

    # ── 5. 写 RUN_SUMMARY ──
    write_sop_run_summary(
        session_dir=session_dir,
        user_query=_run_user_query,
        start_time=sop_start,
        sop_elapsed=sop_elapsed,
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
        saved_sop_id = state["matched_sop_id"]
        saved_action = state.get("current_action", state.get("user_instruction", ""))
        saved_long_term = state.get("long_term_intent", "")

        is_resume = detect_interrupt_resume(state)

        if is_resume:
            # 保留 sop_plan_steps（含进度标记）和 task_status="INTERRUPT"
            resume_state_fields(state, saved_action, saved_long_term)
        else:
            try:
                state = load_sop_and_init_state(
                    state, resources.sop_dir, valid_tool_ids,
                    saved_sop_id, saved_action, saved_long_term,
                )
            except ValueError as e:
                result.status = "error"
                result.sop_id = saved_sop_id
                result.error = f"SOP 加载失败: {e}"
                return result

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
        record_compactor_summaries(state)

        # 保存 RUN_SUMMARY 所需字段（reset_sop_state 会清除）
        _run_user_query = state.get("current_action", "")

        # FINISH 后清除执行状态，避免残留 INTERRUPT 干扰后续执行
        if final_task_status == "FINISH":
            state = reset_sop_state(state)

        # ── 5. 写 RUN_SUMMARY ──
        write_sop_run_summary(
            session_dir=session_dir,
            user_query=_run_user_query,
            start_time=t_start,
            sop_elapsed=sop_elapsed,
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
