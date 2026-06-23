import asyncio
import sys

from rich.console import Console

from graph.Builder import build_graph
from utils.LLMResources import initialize_resources
from utils.cancel_token import reset_cancel
from utils.tts_engine import speak_async, preload as preload_tts, is_loaded as tts_is_loaded
from utils.debug_logger import set_session_dir
from llm_nodes.UserCoordinatorNode import user_coordinator_node
from llm_nodes.ChatCompactorNode import compactor_node
from llm_nodes.ProblemAnalyzerNode import problem_analyzer_node
from llm_nodes.SopSummarizerNode import sop_summarizer_node
from tools.ToolDispatcher import ToolDispatcher
from repl import (
    # State
    create_initial_state,
    # Commands
    ReplCompleter,
    REPL_COMMANDS,
    # Session
    create_session_dir,
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
    create_input_field,
    create_top_status_bar,
    create_status_bar,
    create_root_container,
    create_layout,
    build_application,
    # Controllers
    save_current_if_dirty,
    # Keybindings
    create_keybindings,
)
from repl.repl_context import REPLContext
from repl.execution.input_handler import (
    handle_user_input,
    repl_set_status,
    repl_sync_analysis_indicator,
)

console = Console()


def _make_composite_executor():
    """工厂函数：返回 composite 工具的执行回调（闭包延迟导入 execute_sop_flow）。

    ToolDispatcher.dispatch_composite() 将 tool_id/args + exec_kwargs 透传至此，
    回调负责设置 state["matched_sop_id"] / state["tool_call"] 并委派给 execute_sop_flow。
    """
    async def _exec(sop_id, args, **exec_kwargs):
        from repl.execution.execution_controller import execute_sop_flow
        state = exec_kwargs.pop("state", {})
        state["matched_sop_id"] = sop_id
        if args:
            args_str = ", ".join(
                f"{k}={repr(v)}" for k, v in args.items()
            )
            state["tool_call"] = f"{sop_id}({args_str})"
        else:
            state["tool_call"] = f"{sop_id}()"
        return await execute_sop_flow(state=state, **exec_kwargs)
    return _exec


async def run_repl():
    """REPL 主循环：Application(full_screen=False) 常驻输入区 + patch_stdout 分流输出。"""

    # ── 0. 重置取消令牌 ────────────────────────────────────────
    reset_cancel()

    # ── 1. 初始化资源 ──────────────────────────────────────────
    console.print("[dim]正在初始化 LLM 资源与知识库...[/dim]")
    resources = initialize_resources()

    # ── 2. 编译 SOP 执行图 ──────────────────────────────────────
    app_graph = build_graph(resources)

    # ── 3. 创建节点可调用对象 ────────────────────────────────────
    user_coordinator_fn = user_coordinator_node(resources)
    compactor_fn = compactor_node(resources)
    problem_analyzer_fn = problem_analyzer_node(resources)
    sop_summarizer_fn = sop_summarizer_node(resources)
    tool_dispatcher = ToolDispatcher(
        tools_df=resources.tools_df,
        sops_df=resources.sops_df,
        composite_executor=_make_composite_executor(),
    )

    # ── 4. 会话目录 ────────────────────────────────────────────
    session_dir = create_session_dir()
    set_session_dir(session_dir)
    console.print(f"[dim]会话目录: {session_dir}[/dim]")

    # ── 5. 初始 State ───────────────────────────────────────────
    all_sop_ids = list(resources.sops_df["SOP_ID"].tolist())
    state = create_initial_state("", session_dir, all_sop_ids)
    valid_tool_ids = set(resources.tools_df["Tool_ID"].tolist()) \
                   | set(resources.sops_df["SOP_ID"].tolist())

    # ── 6. TTS 预加载 ──────────────────────────────────────────
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

    # ── 9. 共享上下文（替代原 22 个闭包变量）─────────────────────
    ctx = REPLContext(
        resources=resources,
        app_graph=app_graph,
        session_dir=session_dir,
        user_coordinator_fn=user_coordinator_fn,
        compactor_fn=compactor_fn,
        problem_analyzer_fn=problem_analyzer_fn,
        sop_summarizer_fn=sop_summarizer_fn,
        tool_dispatcher=tool_dispatcher,
        state=state,
        valid_tool_ids=valid_tool_ids,
        console=console,
        top_status_data=top_status_data,
        status_data=status_data,
        picker_state=picker_state,
        sop_picker_state=sop_picker_state,
        config_picker_state=config_picker_state,
        command_hint_state=command_hint_state,
    )

    # ── 10. 按键绑定 ────────────────────────────────────────────
    kb = create_keybindings(
        input_field, ctx.flags, ctx.confirm_event, ctx.confirm_value,
        picker_state, picker_filter,
        sop_picker_state, sop_picker_filter,
        config_picker_state, config_picker_filter,
        command_hint_state, command_hint_filter,
        lambda text: handle_user_input(ctx, text),
    )

    ctx.app = build_application(layout, kb)
    ctx.input_field = input_field

    # Shift+Tab → 切换分析模式
    @kb.add("s-tab")
    def _toggle_analysis(event):
        cfg = get_config()
        new_val = not cfg.get("analyzer_enabled", False)
        apply_config({"analyzer_enabled": new_val})
        repl_sync_analysis_indicator(ctx)

    # 初始化分析模式指示器
    repl_sync_analysis_indicator(ctx)

    # ── 11. 启动 Application ────────────────────────────────────
    try:
        await ctx.app.run_async()
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
        sys.argv.pop(1)
        _run_headless_cli()
    else:
        asyncio.run(run_repl())

if __name__ == "__main__":
    main()
