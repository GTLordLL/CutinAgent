"""
prompt_toolkit + Rich REPL Demo

演示 prompt_toolkit（输入层）+ Rich（输出层）结合效果。
模拟 CutinAgent 的完整交互流程：输入 → 流式输出 → 消息展示。
"""

import asyncio
import time
import random
from concurrent.futures import ThreadPoolExecutor

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import Completer, Completion
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.styles import Style

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich.live import Live
from rich.layout import Layout
from rich.table import Table
from rich import box

# ── 命令补全 ──────────────────────────────────────────────────

_REPL_COMMANDS = ["/help", "/sops", "/history", "/clear", "/styles", "/exit", "/quit"]

class ReplCompleter(Completer):
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            for cmd in _REPL_COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))

# ── 输入样式 ──────────────────────────────────────────────────

INPUT_STYLE = Style.from_dict({
    "prompt": "bold",
    "command": "#8888cc",
})

# ── 快捷键 ────────────────────────────────────────────────────

def create_keybindings():
    kb = KeyBindings()

    @kb.add("escape")
    def _(event):
        """Esc 清空输入。"""
        event.current_buffer.text = ""

    return kb

# ── 输出工具函数 ──────────────────────────────────────────────

console = Console()

def print_welcome():
    """打印欢迎 Banner。"""
    banner = Panel(
        Text("CutinAgent REPL — 人机协作模式\n/help 查看命令  /exit 退出",
             style="bold", justify="center"),
        box=box.HEAVY,
        padding=(1, 2),
    )
    console.print(banner)

def print_user_message(text: str):
    """用户消息 — 左侧竖线标记。"""
    msg = Text(text)
    msg.stylize("bold")
    panel = Panel(msg, border_style="", padding=(0, 1))
    console.print("▌", end="")
    console.print(panel)

def print_assistant_message(text: str):
    """助手消息 — Markdown 渲染。"""
    md = Markdown(text)
    console.print(md)

def print_tool_message(text: str):
    """工具调用/结果消息。"""
    panel = Panel(
        text,
        title="🔧 Tool",
        title_align="left",
        box=box.SQUARE,
        padding=(0, 1),
    )
    console.print(panel)

def print_system_message(text: str):
    """系统消息 — 斜体。"""
    t = Text(text, style="italic dim")
    console.print(f"  {t}")

def print_thinker_section(thinker_text: str, formatter_text: str = ""):
    """Thinker/Formatter 折叠区域（模拟可展开）。"""
    lines = thinker_text.strip().split("\n")
    collapsed = lines[0] if lines else thinker_text[:80]
    panel = Panel(
        collapsed + "\n...",
        title="🧠 Thinker",
        title_align="left",
        box=box.SQUARE,
        padding=(0, 1),
    )
    console.print(panel)
    if formatter_text:
        console.print(Panel(
            formatter_text,
            title="📋 Formatter",
            title_align="left",
            box=box.SQUARE,
            padding=(0, 1),
        ))

def print_step_progress(steps: list[dict]):
    """步骤进度条。"""
    table = Table(box=None, padding=(0, 0), show_header=False, show_edge=False)
    table.add_column("", width=3)
    for step in steps:
        status = step["status"]
        name = step["name"]
        if status == "done":
            table.add_column(f"[strike]{name}[/strike]")
        elif status == "current":
            table.add_column(f"[bold reverse] {name} [/bold reverse]")
        elif status == "skipped":
            table.add_column(f"[strike italic dim]{name}[/strike italic dim]")
        else:
            table.add_column(f"[dim]{name}[/dim]")
    console.print(table)

def print_status_bar(sop_name: str, round_num: int, tokens: int):
    """状态栏。"""
    left = Text(f" SOP: {sop_name} ", style="bold reverse")
    right = Text(f" round={round_num}  tokens={tokens} ", style="dim")
    bar = Text()
    bar.append(left)
    bar.append("─" * (console.width - len(left.plain) - len(right.plain)))
    bar.append(right)
    console.print(bar)

def print_styles_demo():
    """展示 Rich 所有常用样式。"""
    # ── 文字样式 ──
    console.print()
    console.print(Panel("Rich 常用样式一览", style="bold", box=box.HEAVY, padding=(0, 2)))

    text_styles = [
        ("bold", "bold"),
        ("dim", "dim"),
        ("italic", "italic"),
        ("underline", "underline"),
        ("strike", "strike"),
        ("reverse", "reverse"),
        ("blink", "blink"),
    ]
    for name, style in text_styles:
        console.print(Text(f"  {name:<12} → ", style="default"), Text(f"The quick brown fox jumps over the lazy dog", style=style))

    console.print()

    # ── 前景色 ──
    fg_colors = [
        "red", "green", "blue", "yellow", "magenta", "cyan", "white", "black",
        "bright_red", "bright_green", "bright_blue", "bright_yellow",
        "bright_magenta", "bright_cyan", "bright_white", "bright_black",
    ]
    console.print("[bold]前景色 (color)[/bold]")
    for c in fg_colors:
        console.print(Text(f"  {c:<16} → ", style="default"), Text("The quick brown fox jumps over the lazy dog", style=c))
    console.print()

    # ── 背景色 ──
    bg_colors = [
        "on_red", "on_green", "on_blue", "on_yellow", "on_magenta", "on_cyan",
        "on_bright_red", "on_bright_green", "on_bright_blue", "on_bright_yellow",
        "on_bright_magenta", "on_bright_cyan",
    ]
    console.print("[bold]背景色 (on_color)[/bold]")
    for c in bg_colors:
        console.print(f"  {c:<20} → [{c}]  The quick brown fox  [/]")
    console.print()

    # ── 组合样式 ──
    console.print("[bold]组合样式[/bold]")
    combos = [
        "bold red", "italic green", "underline blue",
        "bold underline yellow", "dim italic",
        "reverse bold cyan", "strike bright_red",
    ]
    for c in combos:
        console.print(Text(f"  {c:<32} → ", style="default"), Text("The quick brown fox", style=c))
    # 含背景色的用 markup
    bg_combos = [
        ("bold on_green", "bold on_green"),
        ("white on_blue", "white on_blue"),
        ("bright_yellow on_magenta", "bright_yellow on_magenta"),
        ("underline bright_cyan on_bright_black", "underline bright_cyan on_bright_black"),
    ]
    for c, _ in bg_combos:
        console.print(f"  {c:<32} → [{c}]The quick brown fox[/]")
    console.print()

    # ── Markdown 内联样式 ──
    console.print("[bold]Rich Markdown 内联样式[/bold]")
    md_table = Table(box=box.SQUARE, padding=(0, 1))
    md_table.add_column("Markup", style="dim")
    md_table.add_column("效果")
    examples = [
        ("[bold]bold[/bold]", "[bold]bold text[/bold]"),
        ("[dim]dim[/dim]", "[dim]dim text[/dim]"),
        ("[italic]italic[/italic]", "[italic]italic text[/italic]"),
        ("[underline]underline[/underline]", "[underline]underline text[/underline]"),
        ("[strike]strike[/strike]", "[strike]strike text[/strike]"),
        ("[reverse]reverse[/reverse]", "[reverse]reverse text[/reverse]"),
        ("[red]red[/red]", "[red]red text[/red]"),
        ("[bold red]bold red[/bold red]", "[bold red]bold red text[/bold red]"),
        ("[on_blue]on_blue[/on_blue]", "[on_blue]blue background[/on_blue]"),
        ("[link=https://example.com]link[/link]", "[link=https://example.com]clickable link[/link]"),
    ]
    for markup, effect in examples:
        md_table.add_row(markup, effect)
    console.print(md_table)

# ── 模拟流式输出 ──────────────────────────────────────────────

def simulate_stream(text: str, delay: float = 0.02):
    """用 Rich Live 模拟 token 级流式输出。"""
    with Live(Text(""), console=console, refresh_per_second=60, transient=False) as live:
        accumulated = ""
        words = text.split(" ")
        for i, word in enumerate(words):
            prefix = " " if i > 0 else ""
            for char in prefix + word:
                accumulated += char
                live.update(Text(accumulated, style="default"))
                time.sleep(delay)
            # 偶尔稍长停顿，更真实
            if random.random() < 0.1:
                time.sleep(delay * 5)

    console.print()  # 换行

# ── / 命令处理 ────────────────────────────────────────────────

def handle_command(cmd: str) -> tuple[bool, str | None]:
    """返回 (handled, message)。handled=False 表示不是命令。"""
    cmd = cmd.strip()
    if cmd in ("/exit", "/quit"):
        return True, "再见！"
    if cmd == "/help":
        msg = "\n".join([
            "**CutinAgent REPL 命令**",
            "",
            "| 命令 | 说明 |",
            "|------|------|",
            "| `/help` | 显示帮助 |",
            "| `/sops` | 列出所有可用 SOP |",
            "| `/history` | 显示当前对话与执行历史 |",
            "| `/clear` | 清除对话历史 |",
            "| `/styles` | 展示 Rich 所有常用样式 |",
            "| `/exit` | 退出 REPL |"
            "",
            "直接输入消息可与 Agent 对话。",
        ])
        return True, msg
    if cmd == "/sops":
        msg = "\n".join([
            "**可用 SOP 列表**",
            "",
            "- `GIT_SMART_COMMIT` — 智能生成 git commit 信息并提交",
            "- `GIT_BRANCH_CLEANUP` — 清理过期的已合并分支",
            "- `GIT_PR_CREATE` — 生成 PR 描述并创建 GitHub Pull Request",
        ])
        return True, msg
    if cmd == "/history":
        msg = "> 当前对话为空（Demo 模式）"
        return True, msg
    if cmd == "/styles":
        print_styles_demo()
        return True, None
    if cmd == "/clear":
        return True, "对话历史已清除。"
    return False, None

# ── 模拟 Thinker 推理 ──────────────────────────────────────────

THINKER_DEMO = (
    "我需要理解用户的意图。用户说'你好'，这是一个简单的问候。"
    "根据 SOP_LIBRARY，当前没有匹配的 SOP 需要执行。"
    "因此我应该输出 CHAT_MESSAGE，直接回复用户的问候。"
)

FORMATTER_DEMO = """\
{
  "output_type": "CHAT_MESSAGE",
  "message": "你好！我是 CutinAgent，一个 SOP 驱动的 AI 助手。请问有什么可以帮助你的？",
  "matched_sop_id": null
}"""

STEPS_DEMO = [
    {"name": "分析意图", "status": "done"},
    {"name": "匹配SOP", "status": "done"},
    {"name": "执行步骤1", "status": "current"},
    {"name": "执行步骤2", "status": "pending"},
    {"name": "生成报告", "status": "pending"},
]

# ── 主循环 ────────────────────────────────────────────────────

async def main():
    print_welcome()

    session = PromptSession(
        history=InMemoryHistory(),
        completer=ReplCompleter(),
        key_bindings=create_keybindings(),
        style=INPUT_STYLE,
        message=[
            ("class:prompt", "> "),
        ],
    )

    while True:
        try:
            user_input = await session.prompt_async()
        except (EOFError, KeyboardInterrupt):
            console.print("\n再见！")
            break

        user_input = user_input.strip()
        if not user_input:
            continue

        # / 命令分发
        handled, msg = handle_command(user_input)
        if msg == "再见！":
            console.print(f"[bold]{msg}[/bold]")
            break
        if handled:
            console.print(f"\n{msg}")
            console.print()
            continue

        # ── 模拟完整交互流程 ──

        # 1. 显示用户输入
        console.print()
        print_user_message(user_input)

        # 2. 模拟 Thinker 流式推理
        console.print()
        print_thinker_section(THINKER_DEMO, FORMATTER_DEMO)

        # 3. 模拟步骤进度
        console.print()
        print_step_progress(STEPS_DEMO)

        # 4. 模拟助手流式回复
        console.print()
        assistant_reply = (
            "你好！我是 **CutinAgent**，一个 SOP 驱动的 AI 助手。\n\n"
            "我可以帮助你完成以下任务：\n"
            "- 📝 智能 Git 提交信息生成\n"
            "- 📊 每日工作总结\n"
            "- 🔧 Linux 系统诊断\n\n"
            "请问有什么可以帮助你的？"
        )
        print_assistant_message(assistant_reply)

        # 5. 状态栏
        console.print()
        print_status_bar("CHAT_MESSAGE", round_num=3, tokens=420)

    console.print("\n[dim]会话已结束。[/dim]")


if __name__ == "__main__":
    asyncio.run(main())
