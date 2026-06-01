import asyncio
import shutil
import time
from datetime import datetime

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import has_focus
from prompt_toolkit.patch_stdout import patch_stdout

from rich.console import Console
from rich.panel import Panel

from graph.Builder import build_graph
from utils.LLMResources import initialize_resources
from utils.sop_loader import load_sop_markdown
from utils.debug_logger import set_session_dir
from llm_nodes.UserCoordinatorNode import user_coordinator_node
from llm_nodes.TaskCompactorNode import task_compactor_node
from llm_nodes.ChatCompactorNode import chat_compactor_node
from data_nodes.VariableStore import clear as clear_variables
from repl import (
    create_initial_state,
    create_session_dir,
    dispatch_repl_command,
    reset_sop_state,
    run_sop_graph,
    write_run_summary,
    ReplCompleter,
    print_welcome,
    print_user_message,
    print_agent_message,
    print_command_result,
    create_input_field,
    create_top_status_bar,
    create_status_bar,
    create_root_container,
    create_layout,
    build_application,
)

console = Console()


async def run_repl():
    """REPL 主循环：Application(full_screen=False) 常驻输入区 + patch_stdout 分流输出。

    LLM 节点为同步调用，通过 run_in_executor 在线程池中运行，
    保证主事件循环不阻塞，patch_stdout 可实时 flush 流式 token。
    """
    # 1. 初始化资源
    console.print("[dim]正在初始化 LLM 资源与知识库...[/dim]")
    resources = initialize_resources()

    # 2. 编译 SOP 执行图（3 节点内循环）
    app_graph = build_graph(resources)

    # 3. 创建 UserCoordinator、TaskCompactor 和 ChatCompactor 可调用对象
    user_coordinator_fn = user_coordinator_node(resources)
    task_compactor_fn = task_compactor_node(resources)
    chat_compactor_fn = chat_compactor_node(resources)

    # 4. 创建会话目录
    session_dir = create_session_dir()
    set_session_dir(session_dir)
    console.print(f"[dim]会话目录: {session_dir}[/dim]")

    # 5. 初始化 state
    state = create_initial_state("", session_dir, resources.sop_library_text)
    valid_tool_ids = set(resources.tools_df["Tool_ID"].tolist())

    # 6. 欢迎界面
    console.print()
    print_welcome(console)

    # ── Application 组件 ────────────────────────────────────────

    input_field = create_input_field(completer=ReplCompleter())
    top_status_control, top_status_data = create_top_status_bar()
    status_control, status_data = create_status_bar()

    root = create_root_container(input_field, top_status_control, top_status_data, status_control)
    layout = create_layout(root, input_field)

    # 确认流程状态
    confirm_event = asyncio.Event()
    confirm_value = {}

    # 标记
    flag_processing = False     # True = 正在处理输入，拒绝新输入
    flag_waiting_confirm = False  # True = 当前 Enter 应作为确认回复

    # ── 按键绑定 ────────────────────────────────────────────────

    kb = KeyBindings()

    @kb.add("enter", filter=has_focus(input_field))
    def _on_enter(event):
        nonlocal flag_waiting_confirm, flag_processing
        text = input_field.buffer.text
        input_field.buffer.text = ""

        if flag_waiting_confirm:
            confirm_value["text"] = text
            flag_waiting_confirm = False
            confirm_event.set()
        elif flag_processing:
            pass  # 处理中，忽略输入
        elif text.strip():
            flag_processing = True
            event.app.create_background_task(_handle_input(text.strip()))

    @kb.add("c-c")
    def _on_ctrl_c(event):
        event.app.exit(result="exit")

    @kb.add("escape", filter=has_focus(input_field))
    def _on_escape(event):
        input_field.buffer.text = ""

    app = build_application(layout, kb)

    # ── 输入处理逻辑 ────────────────────────────────────────────

    async def _handle_input(user_msg: str):
        nonlocal state, flag_waiting_confirm, flag_processing

        # 在内联写模式中，sys.stdout 所有输出自动渲染到 Application 上方
        with patch_stdout(raw=True):
            try:
                # / 命令分发（不消耗 LLM）
                handled, msg, should_exit = dispatch_repl_command(
                    user_msg, state, resources
                )
                if should_exit:
                    app.exit(result="exit")
                    return
                if handled:
                    # /compact 需要调用 LLM 压缩对话
                    if user_msg.strip().lower().startswith("/compact"):
                        if not state.get("current_dialogue", "").strip():
                            console.print("[dim]没有需要压缩的对话内容。[/dim]")
                        else:
                            console.print("[dim][ChatCompactor] 压缩对话上下文...[/dim]")
                            loop = asyncio.get_running_loop()
                            cc_start = time.time()
                            cc_stop = asyncio.Event()
                            cc_timer = asyncio.create_task(
                                _runtime_timer("ChatCompactor", cc_start, cc_stop)
                            )
                            try:
                                cc_result = await loop.run_in_executor(
                                    None, chat_compactor_fn, state
                                )
                            finally:
                                cc_stop.set()
                                await cc_timer
                                top_status_data["runtime_text"] = ""
                                app.invalidate()
                            cc_elapsed = time.time() - cc_start
                            console.print(f"[dim]ChatCompactor 耗时: {_fmt_elapsed(cc_elapsed)}[/dim]")
                            state.update(cc_result)
                            summary = state.get("chat_conversation_summary", "")
                            if summary:
                                state["conversation_history"] += "\n" + summary
                                state["current_dialogue"] = ""
                                console.print(Panel(
                                    summary,
                                    title="对话压缩结果", title_align="left", padding=(0, 1),
                                ))
                            else:
                                console.print("[dim]对话压缩完成（无新摘要）。[/dim]")
                    else:
                        print_command_result(console, msg)
                        # /clear 后重置 token 显示
                        if user_msg.strip().lower() == "/clear":
                            state["thinker_input_tokens"] = 0
                            status_data["token_info"] = "0 (0.0%) tokens  ".rjust(
                                shutil.get_terminal_size().columns
                            )
                            app.invalidate()
                    return

                # 追加到当前对话
                state["current_dialogue"] += f"User: {user_msg}\n"
                state["user_instruction"] = user_msg
                print_user_message(console, user_msg)

                # 自动压缩：上一轮 Thinker 输入超过 4096 tokens
                if state.get("thinker_input_tokens", 0) > 4096 and state.get("current_dialogue", "").strip():
                    console.print(f"[dim][ChatCompactor] 上下文过长({state['thinker_input_tokens']} tokens)，自动压缩...[/dim]")
                    state["chat_compact_requirement"] = ""
                    loop = asyncio.get_running_loop()
                    cc_start = time.time()
                    cc_stop = asyncio.Event()
                    cc_timer = asyncio.create_task(
                        _runtime_timer("ChatCompactor", cc_start, cc_stop)
                    )
                    try:
                        cc_result = await loop.run_in_executor(
                            None, chat_compactor_fn, state
                        )
                    finally:
                        cc_stop.set()
                        await cc_timer
                        top_status_data["runtime_text"] = ""
                        app.invalidate()
                    cc_elapsed = time.time() - cc_start
                    console.print(f"[dim]ChatCompactor 耗时: {_fmt_elapsed(cc_elapsed)}[/dim]")
                    state.update(cc_result)
                    summary = state.get("chat_conversation_summary", "")
                    if summary:
                        state["conversation_history"] += "\n" + summary
                        state["current_dialogue"] = ""

                # ---- Step 1: UserCoordinator ----
                _set_status("分析中...")
                console.print("[dim][UserCoordinator] 分析中...[/dim]")

                loop = asyncio.get_running_loop()
                coord_start = time.time()
                coord_stop = asyncio.Event()
                coord_timer = asyncio.create_task(
                    _runtime_timer("UserCoordinator", coord_start, coord_stop)
                )
                try:
                    coord_result = await loop.run_in_executor(
                        None, user_coordinator_fn, state
                    )
                finally:
                    coord_stop.set()
                    await coord_timer
                    top_status_data["runtime_text"] = ""
                    app.invalidate()

                coord_elapsed = time.time() - coord_start
                console.print(f"[dim]UserCoordinator 耗时: {_fmt_elapsed(coord_elapsed)}[/dim]")

                await asyncio.sleep(0.3)
                state.update(coord_result)

                # 更新 token 显示
                input_tokens = state.get("thinker_input_tokens", 0)
                ratio = (input_tokens / 8192) * 100
                token_text = f"{input_tokens:,} ({ratio:.1f}%) tokens  "
                status_data["token_info"] = token_text.rjust(shutil.get_terminal_size().columns)
                app.invalidate()

                console.print()
                print_agent_message(console, state["chat_message"])
                state["current_dialogue"] += f"Agent: {state['chat_message']}\n"
                _set_status(state.get("matched_sop_id", ""))

                # ---- Step 2: 判断模式 ----
                if state.get("is_execute") == "true":
                    # 最终确认
                    console.print(Panel(
                        f"[bold]确认执行[/bold]\n"
                        f"SOP: {state['matched_sop_id']}\n"
                        f"行动: {state['current_action']}\n"
                        f"长期计划: {state['long_term_intent']}",
                        title="确认", title_align="left", padding=(0, 1),
                    ))
                    _set_status("确认执行? (y=执行 / n=重新规划 / 或输入补充信息)")

                    confirm = await _wait_confirm()
                    if confirm.lower() != 'y':
                        if confirm.lower() != 'n':
                            user_msg = confirm
                        else:
                            _set_status("请重新描述需求")
                            user_msg = await _wait_confirm()
                            if not user_msg:
                                return
                        state["current_dialogue"] += f"User (feedback): {user_msg}\n"
                        state["user_instruction"] = user_msg
                        return

                    # ---- Step 3: 加载 SOP → 执行 ----
                    try:
                        sop_md = load_sop_markdown(
                            state["matched_sop_id"],
                            resources.sop_dir,
                            valid_tool_ids,
                        )
                    except ValueError as e:
                        console.print(f"[bold red]SOP 加载失败: {e}[/bold red]")
                        state["current_dialogue"] += (
                            f"Agent (error): SOP load failed: {e}\n"
                        )
                        return

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

                    _set_status(f"执行中: {state['matched_sop_id']}")
                    console.print(Panel(
                        f"开始执行 SOP: [bold]{state['matched_sop_id']}[/bold]\n"
                        f"行动: {state['user_instruction']}",
                        title="执行", title_align="left", padding=(0, 1),
                    ))

                    sop_start = time.time()
                    sop_stop = asyncio.Event()
                    sop_timer = asyncio.create_task(
                        _runtime_timer("SOP", sop_start, sop_stop)
                    )
                    try:
                        state, node_timings, final_task_status, total_rounds = (
                            await loop.run_in_executor(
                                None, run_sop_graph, app_graph, state, console
                            )
                        )
                        await asyncio.sleep(0.3)
                    except Exception as e:
                        sop_stop.set()
                        await sop_timer
                        top_status_data["runtime_text"] = ""
                        app.invalidate()
                        console.print(f"[bold red]SOP 执行崩溃: {e}[/bold red]")
                        import traceback
                        traceback.print_exc()
                        state["current_dialogue"] += (
                            f"Agent (error): SOP execution failed: {e}\n"
                        )
                        return

                    sop_elapsed = time.time() - sop_start
                    console.print(Panel(
                        f"状态: {final_task_status}  |  "
                        f"耗时: {sop_elapsed:.2f}s  |  "
                        f"轮次: {total_rounds}",
                        title="SOP 执行完毕", title_align="left", padding=(0, 1),
                    ))
                    _set_status(f"完成: {state['matched_sop_id']}")

                    # ---- Step 4: TaskCompactor ----
                    console.print("[dim][TaskCompactor] 评价与总结中...[/dim]")
                    compactor_result = await loop.run_in_executor(
                        None, task_compactor_fn, state
                    )
                    await asyncio.sleep(0.3)
                    state.update(compactor_result)

                    # 计时结束（SOP + TaskCompactor 总耗时）
                    total_elapsed = time.time() - sop_start
                    sop_stop.set()
                    await sop_timer
                    top_status_data["runtime_text"] = ""
                    app.invalidate()
                    console.print(f"[dim]总耗时 (SOP + TaskCompactor): {_fmt_elapsed(total_elapsed)}[/dim]")

                    console.print()
                    console.print(Panel(
                        state["compactor_evaluation"],
                        title="执行评价", title_align="left", padding=(0, 1),
                    ))

                    _set_status("满意吗? (y/n)")
                    satisfied = await _wait_confirm()

                    if satisfied.lower() == 'y':
                        if state["compactor_conversation_summary"]:
                            state["conversation_history"] += (
                                "\n" + state["compactor_conversation_summary"]
                            )
                        if state["compactor_execution_summary"]:
                            state["execution_history"] += (
                                "\n" + state["compactor_execution_summary"]
                            )
                        state["current_dialogue"] = ""
                        console.print("[dim]总结已记录。请继续下一个任务。[/dim]")
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

            except Exception:
                import traceback
                traceback.print_exc()
            finally:
                flag_processing = False
                _set_status("")

    # ── 辅助函数 ────────────────────────────────────────────────

    def _fmt_elapsed(seconds: float) -> str:
        """格式化耗时：<60s 用 '12s'，>=60s 用 '1m15s'。"""
        if seconds >= 60:
            m = int(seconds // 60)
            s = int(seconds % 60)
            return f"{m}m{s}s"
        return f"{seconds:.0f}s"

    async def _runtime_timer(label: str, start_time: float, stop_event: asyncio.Event):
        """后台定时器：每 0.5s 刷新顶部状态栏的实时耗时。"""
        try:
            while not stop_event.is_set():
                elapsed = time.time() - start_time
                top_status_data["runtime_text"] = f"  {label}: {_fmt_elapsed(elapsed)}"
                app.invalidate()
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass

    def _set_status(text: str):
        status_data["text"] = (
            f"  {text}  " if text else "  CutinAgent REPL — /help 查看命令  "
        )
        app.invalidate()

    async def _wait_confirm() -> str:
        """暂停处理，等待用户在 TextArea 中按 Enter。返回输入文本。"""
        nonlocal flag_waiting_confirm
        flag_waiting_confirm = True
        confirm_event.clear()
        await confirm_event.wait()
        return confirm_value.get("text", "").strip()

    # ── 启动 Application ─────────────────────────────────────────

    try:
        await app.run_async()
    except asyncio.CancelledError:
        pass
    finally:
        console.print("\n[bold]再见！[/bold]")


if __name__ == "__main__":
    asyncio.run(run_repl())
