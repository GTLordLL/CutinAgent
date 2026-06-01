import asyncio
import shutil
import traceback

from prompt_toolkit.patch_stdout import patch_stdout

from rich.console import Console

from graph.Builder import build_graph
from utils.LLMResources import initialize_resources
from utils.debug_logger import set_session_dir
from llm_nodes.UserCoordinatorNode import user_coordinator_node
from llm_nodes.TaskCompactorNode import task_compactor_node
from llm_nodes.ChatCompactorNode import chat_compactor_node
from repl import (
    # State
    create_initial_state,
    # Commands
    dispatch_repl_command,
    CmdSignal,
    ReplCompleter,
    # Session
    create_session_dir,
    generate_session_id,
    create_picker_state,
    get_picker_condition,
    create_picker_control,
    # SOP Picker
    create_sop_picker_state,
    get_sop_picker_condition,
    create_sop_picker_control,
    # UI
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
    # Controllers
    run_llm_node,
    run_chat_compactor,
    try_auto_compact,
    save_current_if_dirty,
    handle_new_session,
    handle_show_picker,
    handle_load_session,
    handle_show_sop_picker,
    execute_sop_flow,
    create_keybindings,
)

console = Console()


async def run_repl():
    """REPL 主循环：Application(full_screen=False) 常驻输入区 + patch_stdout 分流输出。"""

    # ── 1. 初始化资源 ──────────────────────────────────────────
    console.print("[dim]正在初始化 LLM 资源与知识库...[/dim]")
    resources = initialize_resources()

    # ── 2. 编译 SOP 执行图 ──────────────────────────────────────
    app_graph = build_graph(resources)

    # ── 3. 创建节点可调用对象 ────────────────────────────────────
    user_coordinator_fn = user_coordinator_node(resources)
    task_compactor_fn = task_compactor_node(resources)
    chat_compactor_fn = chat_compactor_node(resources)

    # ── 4. 会话目录 ────────────────────────────────────────────
    session_dir = create_session_dir()
    set_session_dir(session_dir)
    console.print(f"[dim]会话目录: {session_dir}[/dim]")

    # ── 5. 初始 State ───────────────────────────────────────────
    all_sop_ids = list(resources.sops_df["SOP_ID"].tolist())
    state = create_initial_state("", session_dir, all_sop_ids)
    valid_tool_ids = set(resources.tools_df["Tool_ID"].tolist())

    # ── 6. 欢迎界面 ─────────────────────────────────────────────
    console.print()
    print_welcome(console)

    # ── 7. UI 组件 ──────────────────────────────────────────────
    picker_state = create_picker_state()
    sop_picker_state = create_sop_picker_state()
    input_field = create_input_field(completer=ReplCompleter())
    top_status_control, top_status_data = create_top_status_bar()
    status_control, status_data = create_status_bar()

    picker_filter = get_picker_condition(picker_state)
    sop_picker_filter = get_sop_picker_condition(sop_picker_state)
    root = create_root_container(
        input_field, top_status_control, top_status_data, status_control,
        picker_control=create_picker_control(picker_state),
        picker_filter=picker_filter,
        sop_picker_control=create_sop_picker_control(sop_picker_state),
        sop_picker_filter=sop_picker_filter,
    )
    layout = create_layout(root, input_field)

    # ── 8. 状态标记 ────────────────────────────────────────────
    confirm_event = asyncio.Event()
    confirm_value = {}
    flags = {"processing": False, "waiting_confirm": False}

    # ── 9. 辅助函数 ────────────────────────────────────────────
    def _set_status(text: str):
        status_data["text"] = (
            f"  {text}  " if text else "  CutinAgent REPL — /help 查看命令  "
        )
        app.invalidate()

    async def _wait_confirm() -> str:
        flags["waiting_confirm"] = True
        confirm_event.clear()
        await confirm_event.wait()
        return confirm_value.get("text", "").strip()

    # ── 10. 输入处理逻辑 ───────────────────────────────────────
    async def _handle_input(user_msg: str):
        # patch_stdout：所有输出自动渲染到 Application 上方
        with patch_stdout(raw=True):
            try:
                # --- / 命令分发 --------------------------------------------------
                handled, msg, should_exit = dispatch_repl_command(
                    user_msg, state, resources
                )
                if should_exit:
                    app.exit(result="exit")
                    return

                if handled:
                    # /clear → 新会话
                    if msg == CmdSignal.NEW_SESSION:
                        await handle_new_session(state, status_data, app, console)
                        return

                    # /resume → 会话选择器
                    if msg == CmdSignal.SHOW_PICKER:
                        await handle_show_picker(
                            picker_state, state, status_data, app, console
                        )
                        return

                    # /resume <id> → 直接加载
                    if msg.startswith(CmdSignal.LOAD_SESSION_PREFIX):
                        session_id = msg.split(":", 1)[1]
                        await handle_load_session(
                            session_id, state, status_data, app, console
                        )
                        return

                    # /sops → SOP 选择器
                    if msg == CmdSignal.SHOW_SOP_PICKER:
                        await handle_show_sop_picker(
                            sop_picker_state, state, resources, status_data,
                            app, console
                        )
                        return

                    # /compact → 手动压缩
                    if user_msg.strip().lower().startswith("/compact"):
                        await run_chat_compactor(
                            chat_compactor_fn, state, top_status_data,
                            app, console, triggered_by="manual"
                        )
                    else:
                        print_command_result(console, msg)
                    return

                # --- 普通消息 ----------------------------------------------------

                # 追加到当前对话
                state["current_dialogue"] += f"User: {user_msg}\n"
                state["user_instruction"] = user_msg
                print_user_message(console, user_msg)

                # 首次输入：自动命名 + 生成 session_id
                if not state.get("session_name", ""):
                    clean = user_msg.strip()
                    state["session_name"] = clean[:10] if clean else "Unnamed"
                if not state.get("session_id", ""):
                    state["session_id"] = generate_session_id()

                # 自动压缩：上一轮 Thinker 输入超过 4096 tokens
                await try_auto_compact(
                    state, chat_compactor_fn, top_status_data, app, console
                )

                # --- UserCoordinator -------------------------------------------
                _set_status("分析中...")
                console.print("[dim][UserCoordinator] 分析中...[/dim]")

                coord_result, _elapsed = await run_llm_node(
                    "UserCoordinator", user_coordinator_fn, state,
                    top_status_data, app, console
                )

                await asyncio.sleep(0.3)
                state.update(coord_result)

                # 更新 token 显示
                input_tokens = state.get("thinker_input_tokens", 0)
                ratio = (input_tokens / 8192) * 100
                token_text = f"{input_tokens:,} ({ratio:.1f}%) tokens  "
                status_data["token_info"] = token_text.rjust(
                    shutil.get_terminal_size().columns
                )
                app.invalidate()

                console.print()
                print_agent_message(console, state["chat_message"])
                state["current_dialogue"] += f"Agent: {state['chat_message']}\n"
                _set_status(state.get("matched_sop_id", ""))

                # --- 判断模式 --------------------------------------------------
                if state.get("is_execute") == "true":
                    result = await execute_sop_flow(
                        state, resources, app_graph, valid_tool_ids,
                        task_compactor_fn, session_dir,
                        top_status_data, status_data, app, console,
                        _set_status, _wait_confirm,
                    )
                    # execute_sop_flow 返回 feedback dict 表示用户拒绝执行
                    if isinstance(result, dict) and "feedback" in result:
                        user_msg = result["feedback"]
                        if not user_msg:
                            return
                        state["current_dialogue"] += f"User (feedback): {user_msg}\n"
                        state["user_instruction"] = user_msg
                        return

            except Exception:
                traceback.print_exc()
            finally:
                flags["processing"] = False
                _set_status("")

    # ── 11. 按键绑定 ────────────────────────────────────────────
    kb = create_keybindings(
        input_field, flags, confirm_event, confirm_value,
        picker_state, picker_filter,
        sop_picker_state, sop_picker_filter, _handle_input,
    )

    app = build_application(layout, kb)

    # ── 12. 启动 Application ────────────────────────────────────
    try:
        await app.run_async()
    except asyncio.CancelledError:
        pass
    finally:
        save_current_if_dirty(state, console, label="会话")
        console.print("\n[bold]再见！[/bold]")


if __name__ == "__main__":
    asyncio.run(run_repl())
