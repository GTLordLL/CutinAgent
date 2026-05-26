"""REPL UI 渲染函数。

纯 Rich 渲染逻辑，与 prompt_toolkit / LLM 调用无关。
"""

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich import box


def print_welcome(console: Console):
    console.print(Panel(
        Text("CutinAgent REPL — 人机协作模式\n/help 查看命令  /exit 退出",
             style="bold", justify="center"),
        box=box.HEAVY, padding=(1, 2),
    ))


def print_user_message(console: Console, text: str):
    console.print()
    console.print(Text("▌", style="bold"), Panel(text, box=box.SQUARE, padding=(0, 1)))


def print_agent_message(console: Console, text: str):
    console.print(Markdown(text))


def print_command_result(console: Console, text: str):
    console.print(Markdown(text))
