"""REPL 用户输入处理。

将原来 main.py _handle_input 闭包（257行，22个闭包变量）拆分为：
- handle_user_input: 对外入口，3 大分支路由
- _handle_command: 命令分发
- _handle_normal_message: 普通消息主流程
- _run_problem_analyzer_loop: 问题分析员循环
- _run_coordinator_and_execute: 协调器 + SOP 执行

辅助函数（原闭包，现模块级）：
- repl_set_status: 更新状态栏
- repl_sync_analysis_indicator: 同步分析模式指示器
- repl_wait_confirm: 等待用户确认
"""

import asyncio
import shutil
import traceback

from prompt_toolkit.patch_stdout import patch_stdout

from repl.repl_context import REPLContext
from utils.cancel_token import CancellationError, reset_cancel


# ── 模块级辅助函数（原 run_repl 闭包）──────────────────────────

def repl_set_status(ctx: REPLContext, text: str) -> None:
    """更新底部状态栏文本。"""
    ctx.status_data["text"] = (
        f"  {text}  " if text else "  CutinAgent REPL — /help 查看命令  "
    )
    if ctx.app is not None:
        ctx.app.invalidate()


def repl_sync_analysis_indicator(ctx: REPLContext) -> None:
    """同步分析模式指示器到状态栏。"""
    from repl.state.config_manager import get_config
    cfg = get_config()
    ctx.status_data["analysis_mode"] = cfg.get("analyzer_enabled", False)
    if ctx.app is not None:
        ctx.app.invalidate()


async def repl_wait_confirm(ctx: REPLContext) -> str:
    """等待用户输入确认文本。"""
    ctx.flags["waiting_confirm"] = True
    ctx.confirm_event.clear()
    await ctx.confirm_event.wait()
    return ctx.confirm_value.get("text", "").strip()


# ── 输入处理入口 ──────────────────────────────────────────────

async def handle_user_input(ctx: REPLContext, user_msg: str) -> None:
    """处理一条用户输入（替代原来的 _handle_input 闭包）。

    patch_stdout 确保所有输出渲染到 Application 上方。
    路由逻辑：/analyse 拦截 → 命令分发 → 普通消息。

    Args:
        ctx: REPL 共享上下文
        user_msg: 用户输入的原始文本
    """
    with patch_stdout(raw=True):
        try:
            # --- /analyse <message> → 临时开启分析员并处理消息 ----
            analyse_parts = user_msg.strip().split(maxsplit=1)
            if (len(analyse_parts) > 1
                    and analyse_parts[0].lower() == "/analyse"
                    and analyse_parts[1].strip()):
                from repl.state.config_manager import get_config, apply_config
                cfg = get_config()
                if not cfg.get("analyzer_enabled", False):
                    apply_config({"analyzer_enabled": True})
                    repl_sync_analysis_indicator(ctx)
                    ctx.console.print("[dim]问题分析员模式已临时开启。[/dim]")
                user_msg = analyse_parts[1].strip()

            # --- / 命令分发 ---------------------------------------
            handled, reason = await _handle_command(ctx, user_msg)
            if handled:
                return

            # --- 普通消息 -----------------------------------------
            await _handle_normal_message(ctx, user_msg)

        except CancellationError:
            ctx.console.print("\n[bold yellow]已停止当前执行。[/bold yellow]")
            reset_cancel()
        except Exception:
            traceback.print_exc()
        finally:
            ctx.flags["processing"] = False
            repl_set_status(ctx, "")


# ── 命令分发 ──────────────────────────────────────────────────

async def _handle_config_picker_command(ctx: REPLContext) -> None:
    """激活配置选择器，等待用户操作，显示结果。"""
    from repl.pickers.config_picker import activate_config_picker, deactivate_config_picker
    from repl import print_command_result

    activate_config_picker(ctx.config_picker_state)
    ctx.app.invalidate()

    await ctx.config_picker_state["result_event"].wait()
    result = deactivate_config_picker(ctx.config_picker_state)
    ctx.app.invalidate()

    if result.get("action") == "save":
        print_command_result(ctx.console, "设置已保存。")
    elif result.get("action") == "reset":
        print_command_result(ctx.console, "设置已恢复为默认值。")
    else:
        ctx.console.print("[dim]设置未更改。[/dim]")


async def _handle_command(ctx: REPLContext, user_msg: str) -> tuple[bool, str]:
    """分发 / 开头的 REPL 命令。返回 (是否已处理, 原因)。

    如果 user_msg 不是命令或命令未被 dispatch_repl_command 处理，
    返回 (False, "")。
    """
    from repl import dispatch_repl_command, CmdSignal

    handled, msg, should_exit = dispatch_repl_command(
        user_msg, ctx.state, ctx.resources
    )
    if should_exit:
        ctx.app.exit(result="exit")
        return (True, "exit")

    if not handled:
        return (False, "")

    from repl import (
        print_command_result,
        handle_new_session,
        handle_show_picker,
        handle_load_session,
        handle_show_sop_picker,
    )
    from repl.state.config_manager import get_config, apply_config

    # /clear → 新会话
    if msg == CmdSignal.NEW_SESSION:
        await handle_new_session(ctx.state, ctx.status_data, ctx.app, ctx.console)
        return (True, "new_session")

    # /resume → 会话选择器
    if msg == CmdSignal.SHOW_PICKER:
        await handle_show_picker(
            ctx.picker_state, ctx.state, ctx.status_data, ctx.app, ctx.console
        )
        return (True, "show_picker")

    # /resume <id> → 直接加载
    if msg.startswith(CmdSignal.LOAD_SESSION_PREFIX):
        session_id = msg.split(":", 1)[1]
        await handle_load_session(
            session_id, ctx.state, ctx.status_data, ctx.app, ctx.console
        )
        return (True, "load_session")

    # /sops → SOP 选择器
    if msg == CmdSignal.SHOW_SOP_PICKER:
        await handle_show_sop_picker(
            ctx.sop_picker_state, ctx.state, ctx.resources, ctx.status_data,
            ctx.app, ctx.console
        )
        return (True, "show_sop_picker")

    # /config → 全局设置
    if msg == CmdSignal.SHOW_CONFIG_PICKER:
        await _handle_config_picker_command(ctx)
        return (True, "config")

    # /analyse → 切换问题分析员模式
    if msg == CmdSignal.ANALYSE_TOGGLE:
        cfg = get_config()
        new_val = not cfg.get("analyzer_enabled", False)
        apply_config({"analyzer_enabled": new_val})
        repl_sync_analysis_indicator(ctx)
        status_text = "开启" if new_val else "关闭"
        print_command_result(ctx.console, f"问题分析员模式已{status_text}。")
        return (True, "analyse_toggle")

    # /compact → 手动压缩
    if user_msg.strip().lower().startswith("/compact"):
        from repl.execution.compaction_controller import run_chat_compactor
        await run_chat_compactor(
            ctx.chat_compactor_fn, ctx.state, ctx.top_status_data,
            ctx.app, ctx.console, triggered_by="manual"
        )
    else:
        print_command_result(ctx.console, msg)
    return (True, "command")


# ── 普通消息处理 ──────────────────────────────────────────────

async def _handle_normal_message(ctx: REPLContext, user_msg: str) -> None:
    """处理非命令消息：追加对话 → 自动压缩 → 问题分析 → 协调器 → SOP 执行。"""
    from repl import (
        print_user_message, print_agent_message,
    )
    from repl.state.session_manager import generate_session_id
    from repl.execution.compaction_controller import try_auto_compact
    from repl.execution.llm_runner import run_llm_node
    from utils.tts_engine import tts_say

    # 追加到当前对话
    ctx.state["current_dialogue"].append({"role": "user", "content": user_msg})
    ctx.state["user_instruction"] = user_msg
    print_user_message(ctx.console, user_msg)

    # 首次输入：自动命名 + 生成 session_id
    if not ctx.state.get("session_name", ""):
        clean = user_msg.strip()
        ctx.state["session_name"] = clean[:10] if clean else "Unnamed"
    if not ctx.state.get("session_id", ""):
        ctx.state["session_id"] = generate_session_id()

    # 自动压缩：上一轮 Thinker 输入超过 4096 tokens
    await try_auto_compact(
        ctx.state, ctx.chat_compactor_fn, ctx.top_status_data, ctx.app, ctx.console
    )

    # --- Problem Analyzer ---
    await _run_problem_analyzer_loop(ctx)

    # --- UserCoordinator ---
    await _run_coordinator_and_execute(ctx)


# ── 问题分析员辅助 ────────────────────────────────────────────

async def _execute_analyzer_tool_calls(
    ctx: REPLContext, tool_call: str, round_num: int
) -> None:
    """解析并行工具调用并执行，结果追加到 execution_history。"""
    from parsers.tool_call import _split_parallel_calls, parse_single_call

    calls = _split_parallel_calls(tool_call)
    repl_set_status(ctx, f"执行工具: {tool_call[:50]}...")
    for call_str in calls:
        parsed = parse_single_call(call_str)
        if parsed is None:
            ctx.console.print(
                f"[dim][ProblemAnalyzer] 工具调用解析失败: "
                f"{call_str[:60]}[/dim]"
            )
            continue
        tool_id, args = parsed
        ctx.console.print(
            f"[dim][ProblemAnalyzer] 执行: {tool_id}"
            f"({', '.join(f'{k}={v}' for k, v in args.items())})[/dim]"
        )
        result = ctx.tool_dispatcher.dispatch(tool_id, args)
        exec_entry = (
            f"[Analyzer Round {round_num}] "
            f"{tool_id}({', '.join(f'{k}={v}' for k, v in args.items())}): "
            f"status=\"{result.get('status', '?')}\", "
            f"summary=\"{result.get('summary', result.get('conclusion', ''))[:200]}\""
        )
        current_exec = ctx.state.get("execution_history", "")
        ctx.state["execution_history"] = (
            current_exec + "\n" + exec_entry if current_exec else exec_entry
        )


def _append_analyzer_result(ctx: REPLContext) -> None:
    """将问题分析结果合并追加到对话历史。"""
    _as = ctx.state.get("analyzer_current_state", "")
    _au = ctx.state.get("analyzer_my_understanding", "")
    if not _as and not _au:
        return
    _parts = []
    if _as:
        _parts.append(f"当前状态: {_as}")
    if _au:
        _parts.append(f"推断意图: {_au}")
    _analyzer_msg = "\n".join(_parts)
    ctx.state["current_dialogue"].append(
        {"role": "analyzer", "content": _analyzer_msg}
    )
    ctx.console.print(
        "[dim][ProblemAnalyzer] 分析结果已追加到对话历史[/dim]"
    )


# ── 问题分析员循环 ────────────────────────────────────────────

async def _run_problem_analyzer_loop(ctx: REPLContext) -> None:
    """运行问题分析员多轮信息收集循环。

    仅在 analyzer_enabled 配置开启时执行。
    最多运行 analyzer_max_rounds 轮，高置信度时提前退出。
    分析结果追加到 current_dialogue 供 UserCoordinator 参考。
    """
    from repl.state.config_manager import get_config
    from repl.execution.llm_runner import run_llm_node

    cfg = get_config()
    if not cfg.get("analyzer_enabled", False):
        return

    analyzer_rounds = 0
    max_rounds = int(cfg.get("analyzer_max_rounds", 3))

    while analyzer_rounds < max_rounds:
        repl_set_status(ctx, "分析中...")
        ctx.console.print(
            f"[dim][ProblemAnalyzer] 信息收集中... "
            f"(第 {analyzer_rounds + 1}/{max_rounds} 轮)[/dim]"
        )

        analyzer_result, _a_elapsed = await run_llm_node(
            "ProblemAnalyzer", ctx.problem_analyzer_fn, ctx.state,
            ctx.top_status_data, ctx.app, ctx.console
        )
        await asyncio.sleep(0.3)
        ctx.state.update(analyzer_result)

        confidence = ctx.state.get("analyzer_confidence", "low")
        ctx.console.print(
            f"[dim][ProblemAnalyzer] 置信度: {confidence}, "
            f"当前状态: {ctx.state.get('analyzer_current_state', '')[:80]}...[/dim]"
        )

        # 高置信度 → 提前退出
        if confidence == "high":
            my_understanding = ctx.state.get("analyzer_my_understanding", "")
            ctx.console.print(
                f"[dim][ProblemAnalyzer] 高置信度，推断意图: "
                f"{my_understanding[:100]}[/dim]"
            )
            break

        tool_call = ctx.state.get("analyzer_tool_call", "")
        if not tool_call or tool_call.strip().upper() == "NONE":
            ctx.console.print("[dim][ProblemAnalyzer] 无工具调用，退出分析循环。[/dim]")
            break

        await _execute_analyzer_tool_calls(ctx, tool_call, analyzer_rounds + 1)
        analyzer_rounds += 1

    ctx.state["analyzer_rounds_used"] = analyzer_rounds
    _append_analyzer_result(ctx)


# ── 协调器 + SOP 执行 ─────────────────────────────────────────

async def _run_coordinator_and_execute(ctx: REPLContext) -> None:
    """运行 UserCoordinator → TTS 播报 → IS_EXECUTE 判断 → SOP 执行。"""
    from repl import print_agent_message
    from repl.execution.llm_runner import run_llm_node
    from repl.execution.execution_controller import execute_sop_flow
    from utils.tts_engine import tts_say

    repl_set_status(ctx, "分析中...")
    ctx.console.print("[dim][UserCoordinator] 分析中...[/dim]")

    coord_result, _elapsed = await run_llm_node(
        "UserCoordinator", ctx.user_coordinator_fn, ctx.state,
        ctx.top_status_data, ctx.app, ctx.console
    )

    await asyncio.sleep(0.3)
    ctx.state.update(coord_result)

    # 更新 token 显示
    input_tokens = ctx.state.get("thinker_input_tokens", 0)
    ratio = (input_tokens / 8192) * 100
    token_text = f"{input_tokens:,} ({ratio:.1f}%) tokens  "
    ctx.status_data["token_info"] = token_text.rjust(
        shutil.get_terminal_size().columns
    )
    ctx.app.invalidate()

    ctx.console.print()
    print_agent_message(ctx.console, ctx.state["chat_message"])

    # TTS 语音播报（异步，不阻塞后续流程）
    tts_say(ctx.state["chat_message"])

    ctx.state["current_dialogue"].append(
        {"role": "agent", "content": ctx.state["chat_message"]}
    )
    repl_set_status(ctx, ctx.state.get("matched_sop_id", ""))

    # --- 判断模式 ---
    if ctx.state.get("is_execute") == "true":
        result = await execute_sop_flow(
            ctx.state, ctx.resources, ctx.app_graph, ctx.valid_tool_ids,
            ctx.task_compactor_fn, ctx.session_dir,
            ctx.top_status_data, ctx.status_data, ctx.app, ctx.console,
            lambda text: repl_set_status(ctx, text),
            lambda: repl_wait_confirm(ctx),
        )
        # execute_sop_flow 返回 feedback dict 表示用户拒绝执行
        if isinstance(result, dict) and "feedback" in result:
            user_msg = result["feedback"]
            if user_msg:
                ctx.state["current_dialogue"].append(
                    {"role": "feedback", "content": user_msg}
                )
                ctx.state["user_instruction"] = user_msg
