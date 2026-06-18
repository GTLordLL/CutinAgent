"""REPL UI 渲染函数。

纯 Rich 渲染逻辑，与 prompt_toolkit / LLM 调用无关。
"""

from rich.console import Console
from rich.panel import Panel
from rich.markdown import Markdown
from rich.text import Text
from rich import box

from repl.version import __version__


def print_welcome(console: Console):
    import os
    cwd = os.getcwd()


    banner = (
        "     ______         __   _          ___                      __  \n"
        "    / ____/_  __ __/ /_ (_)___     /   | ____  ___  ____  __/ /_ \n"
        "   / /   / / / /_   __// / __ \\   / /| |/ __ `/ _ \\/ __ \\/_  __/ \n"
        "  / /___/ /_/ / / /_  / / / / /  / ___ / /_/ /  __/ / / / / /    \n"
        "  \\____/\\__,_/  |___//_/_/ /_/  /_/  |_\\__, /\\___/_/ /_/ /_/     \n"
        "                                      /____/                     \n"
        f"  https://github.com/GTLordLL/CutinAgent  --  千务小切 {__version__}\n"
    )

    print(f"\033[36m{banner}\033[0m")  # 青色 ANSI，保持原始 print 避免 Rich 颜色错位

    console.print(Text.assemble(
        ("  当前工作目录：", "dim"),
        (f"{cwd}\n", "white"),
        ("  /help 查看命令  /exit 退出", "dim italic"),
    ))



def print_user_message(console: Console, text: str):
    console.print()
    console.print(Text(f"> {text}", style="bold white on bright_black"))
    console.print()


def print_agent_message(console: Console, text: str):
    console.out(text + "\n")


def print_command_result(console: Console, text: str):
    console.print(Markdown(text))
