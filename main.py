import asyncio
import shutil
import sys
import traceback

from prompt_toolkit.patch_stdout import patch_stdout

from rich.console import Console

from graph.Builder import build_graph
from utils.LLMResources import initialize_resources
from utils.tts_engine import speak_async, preload as preload_tts, is_loaded as tts_is_loaded, tts_say
from utils.debug_logger import set_session_dir
from llm_nodes.UserCoordinatorNode import user_coordinator_node
from llm_nodes.TaskCompactorNode import task_compactor_node
from llm_nodes.ChatCompactorNode import chat_compactor_node
from llm_nodes.ProblemAnalyzerNode import problem_analyzer_node
from tools.ToolDispatcher import ToolDispatcher
from parsers.tool_call import _split_parallel_calls, parse_single_call
from repl import (
    # State
    create_initial_state,
    # Commands
    dispatch_repl_command,
    CmdSignal,
    ReplCompleter,
    REPL_COMMANDS,
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
    # Config Picker
    create_config_picker_state,
    get_config_picker_condition,
    create_config_picker_control,
    # Config
    get_config,
    apply_config,
    # Command Hint
    create_command_hint_state,
    get_command_hint_condition,
    create_command_hint_control,
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
    problem_analyzer_fn = problem_analyzer_node(resources)
    tool_dispatcher = ToolDispatcher()

    # ── 4. 会话目录 ────────────────────────────────────────────
    session_dir = create_session_dir()
    set_session_dir(session_dir)
    console.print(f"[dim]会话目录: {session_dir}[/dim]")

    # ── 5. 初始 State ───────────────────────────────────────────
    all_sop_ids = list(resources.sops_df["SOP_ID"].tolist())
    state = create_initial_state("", session_dir, all_sop_ids)
    valid_tool_ids = set(resources.tools_df["Tool_ID"].tolist())

    # ── 6. TTS 预加载（开启时验证 API 连通性，在 banner 前输出）──
    if get_config().get("tts_enabled", False):
        console.print("[dim]正在检测 TTS 服务连通性...[/dim]")
        await preload_tts()
        if tts_is_loaded():
            console.print("[dim]TTS 语音服务已就绪。[/dim]")
        else:
            console.print("[dim]TTS 服务不可用，播报已自动关闭。[/dim]")

    # ── 7. 欢迎界面 ─────────────────────────────────────────────
    console.print()
    print_welcome(console)

    # ── 8. UI 组件 ──────────────────────────────────────────────
    picker_state = create_picker_state()
    sop_picker_state = create_sop_picker_state()
    config_picker_state = create_config_picker_state()
    command_hint_state = create_command_hint_state()
    command_hint_state["commands"] = REPL_COMMANDS
    input_field = create_input_field(completer=ReplCompleter(), state=state)
    top_status_control, top_status_data = create_top_status_bar()
    status_control, status_data = create_status_bar()

    picker_filter = get_picker_condition(picker_state)
    sop_picker_filter = get_sop_picker_condition(sop_picker_state)
    config_picker_filter = get_config_picker_condition(config_picker_state)
    command_hint_filter = get_command_hint_condition(command_hint_state, input_field)
    command_hint_control = create_command_hint_control(command_hint_state, input_field)
    root = create_root_container(
        input_field, top_status_control, top_status_data, status_control,
        picker_control=create_picker_control(picker_state),
        picker_filter=picker_filter,
        sop_picker_control=create_sop_picker_control(sop_picker_state),
        sop_picker_filter=sop_picker_filter,
        config_picker_control=create_config_picker_control(config_picker_state),
        config_picker_filter=config_picker_filter,
        command_hint_control=command_hint_control,
        command_hint_filter=command_hint_filter,
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

    def _sync_analysis_indicator():
        """同步分析模式指示器到状态栏。"""
        cfg = get_config()
        status_data["analysis_mode"] = cfg.get("analyzer_enabled", False)
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
                # --- /analyse <message> → 开启分析员并处理消息 -------------
                # 在命令分发前拦截，使其作为普通消息走完整流程
                _analyse_parts = user_msg.strip().split(maxsplit=1)
                if (len(_analyse_parts) > 1
                        and _analyse_parts[0].lower() == "/analyse"
                        and _analyse_parts[1].strip()):
                    cfg = get_config()
                    if not cfg.get("analyzer_enabled", False):
                        apply_config({"analyzer_enabled": True})
                        _sync_analysis_indicator()
                        console.print("[dim]问题分析员模式已临时开启。[/dim]")
                    user_msg = _analyse_parts[1].strip()

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

                    # /config → 全局设置
                    if msg == CmdSignal.SHOW_CONFIG_PICKER:
                        from repl.config_picker import (
                            activate_config_picker, deactivate_config_picker,
                        )
                        activate_config_picker(config_picker_state)
                        app.invalidate()

                        await config_picker_state["result_event"].wait()
                        result = deactivate_config_picker(config_picker_state)
                        app.invalidate()

                        if result.get("action") == "save":
                            print_command_result(console, "设置已保存。")
                        elif result.get("action") == "reset":
                            print_command_result(console, "设置已恢复为默认值。")
                        else:
                            console.print("[dim]设置未更改。[/dim]")
                        return

                    # /analyse → 切换问题分析员模式
                    if msg == CmdSignal.ANALYSE_TOGGLE:
                        cfg = get_config()
                        new_val = not cfg.get("analyzer_enabled", False)
                        apply_config({"analyzer_enabled": new_val})
                        _sync_analysis_indicator()
                        status_text = "开启" if new_val else "关闭"
                        print_command_result(console, f"问题分析员模式已{status_text}。")
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
                state["current_dialogue"].append({"role": "user", "content": user_msg})
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

                # --- Problem Analyzer (v0.2) -----------------------------------
                cfg = get_config()
                if cfg.get("analyzer_enabled", False):
                    analyzer_rounds = 0
                    max_rounds = int(cfg.get("analyzer_max_rounds", 3))

                    while analyzer_rounds < max_rounds:
                        _set_status("分析中...")
                        console.print(
                            f"[dim][ProblemAnalyzer] 信息收集中... "
                            f"(第 {analyzer_rounds + 1}/{max_rounds} 轮)[/dim]"
                        )

                        analyzer_result, _a_elapsed = await run_llm_node(
                            "ProblemAnalyzer", problem_analyzer_fn, state,
                            top_status_data, app, console
                        )
                        await asyncio.sleep(0.3)
                        state.update(analyzer_result)

                        confidence = state.get("analyzer_confidence", "low")
                        console.print(
                            f"[dim][ProblemAnalyzer] 置信度: {confidence}, "
                            f"当前状态: {state.get('analyzer_current_state', '')[:80]}...[/dim]"
                        )

                        # 高置信度 → 提前退出
                        if confidence == "high":
                            my_understanding = state.get("analyzer_my_understanding", "")
                            console.print(
                                f"[dim][ProblemAnalyzer] 高置信度，推断意图: "
                                f"{my_understanding[:100]}[/dim]"
                            )
                            break

                        tool_call = state.get("analyzer_tool_call", "")
                        if not tool_call or tool_call.strip().upper() == "NONE":
                            console.print("[dim][ProblemAnalyzer] 无工具调用，退出分析循环。[/dim]")
                            break

                        # 解析并行调用，执行工具
                        calls = _split_parallel_calls(tool_call)
                        _set_status(f"执行工具: {tool_call[:50]}...")
                        for call_str in calls:
                            parsed = parse_single_call(call_str)
                            if parsed is None:
                                console.print(
                                    f"[dim][ProblemAnalyzer] 工具调用解析失败: "
                                    f"{call_str[:60]}[/dim]"
                                )
                                continue
                            tool_id, args = parsed
                            console.print(
                                f"[dim][ProblemAnalyzer] 执行: {tool_id}"
                                f"({', '.join(f'{k}={v}' for k, v in args.items())})[/dim]"
                            )
                            result = tool_dispatcher.dispatch(tool_id, args)
                            # 追加工具执行结果到 execution_history
                            exec_entry = (
                                f"[Analyzer Round {analyzer_rounds + 1}] "
                                f"{tool_id}({', '.join(f'{k}={v}' for k, v in args.items())}): "
                                f"status=\"{result.get('status', '?')}\", "
                                f"summary=\"{result.get('summary', result.get('conclusion', ''))[:200]}\""
                            )
                            current_exec = state.get("execution_history", "")
                            state["execution_history"] = (
                                current_exec + "\n" + exec_entry
                                if current_exec
                                else exec_entry
                            )

                        analyzer_rounds += 1

                    state["analyzer_rounds_used"] = analyzer_rounds

                    # 将分析结果合并追加到对话历史，供 UserCoordinator 参考
                    _as = state.get("analyzer_current_state", "")
                    _au = state.get("analyzer_my_understanding", "")
                    if _as or _au:
                        _parts = []
                        if _as:
                            _parts.append(f"当前状态: {_as}")
                        if _au:
                            _parts.append(f"推断意图: {_au}")
                        _analyzer_msg = "\n".join(_parts)
                        state["current_dialogue"].append(
                            {"role": "analyzer", "content": _analyzer_msg}
                        )
                        console.print(
                            f"[dim][ProblemAnalyzer] 分析结果已追加到对话历史[/dim]"
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

                # TTS 语音播报（异步，不阻塞后续流程）
                tts_say(state["chat_message"])

                state["current_dialogue"].append({"role": "agent", "content": state["chat_message"]})
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
                        state["current_dialogue"].append({"role": "feedback", "content": user_msg})
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
        sop_picker_state, sop_picker_filter,
        config_picker_state, config_picker_filter,
        command_hint_state, command_hint_filter,
        _handle_input,
    )

    app = build_application(layout, kb)

    # Shift+Tab → 切换分析模式（状态栏指示器已反馈，无需 console.print）
    @kb.add("s-tab")
    def _toggle_analysis(event):
        cfg = get_config()
        new_val = not cfg.get("analyzer_enabled", False)
        apply_config({"analyzer_enabled": new_val})
        _sync_analysis_indicator()

    # 初始化分析模式指示器
    _sync_analysis_indicator()

    # ── 12. 启动 Application ────────────────────────────────────
    try:
        await app.run_async()
    except asyncio.CancelledError:
        pass
    finally:
        save_current_if_dirty(state, console, label="会话")
        console.print("\n[bold]再见！[/bold]")


def _run_headless_cli():
    """Headless CLI 入口：解析参数并执行。"""
    from cli.parser import build_parser
    from cli.headless_runner import run_headless

    parser = build_parser()
    args = parser.parse_args()
    exit_code = run_headless(args)
    sys.exit(exit_code)


def main():
    """Entry point for pip install -e . console_scripts.

    路由规则：
    - cutin run ...  → Headless CLI 模式
    - cutin           → REPL TUI 模式
    """
    if len(sys.argv) > 1 and sys.argv[1] == "run":
        # 去掉 "run" 子命令，让 argparse 解析剩余参数
        sys.argv.pop(1)
        _run_headless_cli()
    else:
        asyncio.run(run_repl())

if __name__ == "__main__":
    main()
