import asyncio
import time
from datetime import datetime

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich import box

from graph.Builder import build_graph
from utils.LLMResources import initialize_resources
from utils.sop_loader import load_sop_markdown
from utils.debug_logger import set_session_dir
from llm_nodes.UserCoordinatorNode import user_coordinator_node
from llm_nodes.CompactorNode import compactor_node
from repl import (
    create_initial_state,
    create_session_dir,
    dispatch_repl_command,
    reset_sop_state,
    run_sop_graph,
    write_run_summary,
)

console = Console()

_REPL_COMMANDS = ["/help", "/sops", "/history", "/clear", "/exit", "/quit"]


# ── prompt_toolkit 组件 ───────────────────────────────────────

class ReplCompleter(Completer):
    """Tab 补全 / 前缀命令。"""
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            for cmd in _REPL_COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))


def _create_keybindings():
    """Esc 清空输入。"""
    kb = KeyBindings()
    @kb.add("escape")
    def _(event):
        event.current_buffer.text = ""
    return kb


INPUT_STYLE = Style.from_dict({
    "prompt": "bold",
})


# ── 状态栏（prompt_toolkit bottom toolbar）────────────────────

def _make_status_toolbar():
    """返回一个闭包，供 prompt_toolkit bottom_toolbar 使用。"""
    data = {"sop": "", "round": 0, "tokens": 0}

    def set_status(sop: str = "", round_num: int = 0, tokens: int = 0):
        data["sop"] = sop
        data["round"] = round_num
        data["tokens"] = tokens

    def get_toolbar():
        sop = data["sop"]
        rnd = data["round"]
        tok = data["tokens"]
        if sop:
            return f" SOP: {sop}    round={rnd}    tokens={tok} "
        return " CutinAgent REPL — /help 查看命令 "

    return set_status, get_toolbar


# ── Rich 渲染辅助 ─────────────────────────────────────────────

def _print_welcome():
    console.print(Panel(
        Text("CutinAgent REPL — 人机协作模式\n/help 查看命令  /exit 退出",
             style="bold", justify="center"),
        box=box.HEAVY, padding=(1, 2),
    ))


def _print_user_message(text: str):
    console.print()
    console.print(Text("▌", style="bold"), Panel(text, box=box.SQUARE, padding=(0, 1)))


def _print_agent_message(text: str):
    console.print(Markdown(text))


def _print_command_result(text: str):
    console.print(Markdown(text))


async def run_repl():
    """REPL 主循环：资源初始化 → 交互循环
       (UserCoordinator → 确认 → SOP 执行 → Compactor)。
    """
    # 1. 初始化资源
    console.print("[dim]正在初始化 LLM 资源与知识库...[/dim]")
    resources = initialize_resources()

    # 2. 编译 SOP 执行图（3 节点内循环）
    app = build_graph(resources)

    # 3. 创建 UserCoordinator 和 Compactor 可调用对象
    user_coordinator_fn = user_coordinator_node(resources)
    compactor_fn = compactor_node(resources)

    # 4. 创建会话目录
    session_dir = create_session_dir()
    set_session_dir(session_dir)
    console.print(f"[dim]会话目录: {session_dir}[/dim]")

    # 5. 初始化 state
    state = create_initial_state("", session_dir, resources.sop_library_text)
    valid_tool_ids = set(resources.tools_df["Tool_ID"].tolist())

    # 6. 欢迎界面
    console.print()
    _print_welcome()

    # 7. 状态栏 + 输入提示
    set_status, get_toolbar = _make_status_toolbar()

    session = PromptSession(
        history=InMemoryHistory(),
        completer=ReplCompleter(),
        key_bindings=_create_keybindings(),
        style=INPUT_STYLE,
        bottom_toolbar=get_toolbar,
        message=[("class:prompt", "> ")],
    )

    # 8. REPL 循环
    while True:
        try:
            user_msg = (await session.prompt_async()).strip()
        except (EOFError, KeyboardInterrupt):
            console.print("\n[bold]再见！[/bold]")
            break

        if not user_msg:
            continue

        # / 命令分发（在 UserCoordinator 之前拦截，不消耗 LLM）
        handled, msg, should_exit = dispatch_repl_command(user_msg, state, resources)
        if should_exit:
            console.print(f"[bold]{msg}[/bold]")
            break
        if handled:
            _print_command_result(msg)
            continue

        # 追加到当前对话
        state["current_dialogue"] += f"User: {user_msg}\n"
        state["user_instruction"] = user_msg

        # 显示用户消息
        _print_user_message(user_msg)

        # ---- Step 1: UserCoordinator ----
        console.print(Panel("[UserCoordinator] 分析中...", padding=(0, 1)))
        coord_result = user_coordinator_fn(state)
        state.update(coord_result)

        # 显示 Agent 回复
        _print_agent_message(state["chat_message"])
        state["current_dialogue"] += f"Agent: {state['chat_message']}\n"

        # 更新状态栏
        set_status(sop=state.get("matched_sop_id", ""),
                   round_num=state.get("current_round", 0))

        # ---- Step 2: 判断模式 ----
        if state.get("is_execute") == "true":
            # 最终确认模式
            console.print(Panel(
                f"[bold]确认执行[/bold]\n"
                f"SOP: {state['matched_sop_id']}\n"
                f"行动: {state['current_action']}\n"
                f"长期计划: {state['long_term_intent']}",
                title="确认", title_align="left", padding=(0, 1),
            ))

            confirm = (await session.prompt_async(
                message=[("class:prompt", "确认执行? (y=执行 / n=重新规划 / 或输入补充信息): ")],
            )).strip()

            if confirm.lower() != 'y':
                if confirm.lower() != 'n':
                    user_msg = confirm
                else:
                    user_msg = (await session.prompt_async(
                        message=[("class:prompt", "请重新描述您的需求: ")],
                    )).strip()
                    if not user_msg:
                        continue
                state["current_dialogue"] += f"User (feedback): {user_msg}\n"
                state["user_instruction"] = user_msg
                continue

            # ---- Step 3: 加载 SOP → 执行 SOP 图 ----
            try:
                sop_md = load_sop_markdown(state["matched_sop_id"], resources.sop_dir, valid_tool_ids)
            except ValueError as e:
                console.print(f"[bold red]SOP 加载失败: {e}[/bold red]")
                state["current_dialogue"] += f"Agent (error): SOP load failed: {e}\n"
                continue

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
                "retry_limit": int(sop_md.get("retry_limit", "3").strip()) if sop_md.get("retry_limit", "3").strip().isdigit() else 3,
                "user_instruction": saved_action,
                "current_action": saved_action,
                "long_term_intent": saved_long_term,
                "task_status": "ONGOING",
                "current_round": 0,
            })

            set_status(sop=state["matched_sop_id"], round_num=0)

            console.print(Panel(
                f"开始执行 SOP: [bold]{state['matched_sop_id']}[/bold]\n"
                f"行动: {state['user_instruction']}",
                title="执行", title_align="left", padding=(0, 1),
            ))

            sop_start = time.time()
            try:
                state, node_timings, final_task_status, total_rounds = run_sop_graph(app, state, console=console)
            except Exception as e:
                console.print(f"[bold red]SOP 执行崩溃: {e}[/bold red]")
                import traceback
                traceback.print_exc()
                state["current_dialogue"] += f"Agent (error): SOP execution failed: {e}\n"
                continue

            sop_elapsed = time.time() - sop_start
            console.print(Panel(
                f"状态: {final_task_status}  |  "
                f"耗时: {sop_elapsed:.2f}s  |  "
                f"轮次: {total_rounds}",
                title="SOP 执行完毕", title_align="left", padding=(0, 1),
            ))

            # 更新状态栏
            set_status(sop=state["matched_sop_id"], round_num=total_rounds)

            # ---- Step 4: Compactor ----
            console.print("[dim][Compactor] 评价与总结中...[/dim]")
            compactor_result = compactor_fn(state)
            state.update(compactor_result)

            console.print(Panel(
                state["compactor_evaluation"],
                title="执行评价", title_align="left", padding=(0, 1),
            ))

            satisfied = (await session.prompt_async(
                message=[("class:prompt", "对执行结果满意吗? (y/n): ")],
            )).strip()

            if satisfied.lower() == 'y':
                if state["compactor_conversation_summary"]:
                    state["conversation_history"] += "\n" + state["compactor_conversation_summary"]
                if state["compactor_execution_summary"]:
                    state["execution_history"] += "\n" + state["compactor_execution_summary"]
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

            # 清空状态栏
            set_status(sop="")
        else:
            # 渐进式确认模式：继续循环
            pass


if __name__ == "__main__":
    asyncio.run(run_repl())
