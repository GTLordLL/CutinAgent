from prompt_toolkit.completion import Completer, Completion
from utils.sop_loader import build_sop_library_index
from repl.commands.dialogue_utils import dialogue_to_text

REPL_COMMANDS = ["/help", "/sops", "/history", "/clear", "/compact", "/config", "/resume", "/exit", "/quit", "/analyse"]


class CmdSignal:
    """命令分发信号常量，替代魔法字符串。

    dispatch_repl_command 返回的 msg 与这些常量比较，
    调用方（main.py）据此执行具体操作。
    """
    NEW_SESSION = "new_session"
    SHOW_PICKER = "show_picker"
    LOAD_SESSION_PREFIX = "load_session:"
    SHOW_SOP_PICKER = "show_sop_picker"
    SHOW_CONFIG_PICKER = "show_config_picker"
    ANALYSE_TOGGLE = "analyse_toggle"


class ReplCompleter(Completer):
    """Tab 补全 / 前缀命令。"""
    def get_completions(self, document, complete_event):
        text = document.text_before_cursor
        if text.startswith("/"):
            for cmd in REPL_COMMANDS:
                if cmd.startswith(text):
                    yield Completion(cmd, start_position=-len(text))


def dispatch_repl_command(cmd: str, state: dict, resources) -> tuple:
    """处理 / 前缀命令。返回 (handled, message, should_exit)。"""
    cmd = cmd.strip()
    if not cmd.startswith("/"):
        return False, None, False

    parts = cmd.split(maxsplit=1)
    name = parts[0].lower()

    if name in ("/exit", "/quit"):
        return True, "", True

    if name == "/help":
        return True, _build_help_message(resources), False

    if name == "/sops":
        return True, CmdSignal.SHOW_SOP_PICKER, False

    if name == "/clear":
        return True, CmdSignal.NEW_SESSION, False

    if name == "/history":
        return True, _build_history_message(state), False

    if name == "/resume":
        if len(parts) > 1:
            return True, f"{CmdSignal.LOAD_SESSION_PREFIX}{parts[1]}", False
        return True, CmdSignal.SHOW_PICKER, False

    if name == "/compact":
        requirement = " ".join(parts[1:]) if len(parts) > 1 else ""
        state["chat_compact_requirement"] = requirement
        return True, "正在压缩对话上下文...", False

    if name == "/config":
        return True, CmdSignal.SHOW_CONFIG_PICKER, False

    if name == "/analyse":
        return True, CmdSignal.ANALYSE_TOGGLE, False


    return False, None, False


def _build_help_message(resources) -> str:
    """构建 /help 信息（Markdown 格式）。"""
    lines = [
        "# CutinAgent REPL 命令列表",
        "",
        "| 命令 | 说明 |",
        "|------|------|",
        "| `/help` | 显示此帮助信息 |",
        "| `/sops` | 列出所有可用 SOP (可以选择) |",
        "| `/history` | 显示当前对话与执行历史摘要 |\n"
        "| `/compact [提示]` | 手动压缩对话上下文，可附带压缩要求 |\n"
        "| `/analyse` | 开启/关闭问题分析员模式，自动收集信息辅助诊断 |\n"
        "| `/config` | 修改全局运行时设置（阈值/缓冲/行数/TTS） |",
        "| `/clear` | 保存当前会话并开始新会话 |",
        "| `/resume` | 打开会话选择器，恢复历史会话 |",
        "| `/exit` | 退出 REPL |",
        "",
        "## 可用 SOP",
        "",
    ]
    sop_text = build_sop_library_index(resources.sops_df)
    for line in sop_text.strip().split("\n"):
        lines.append(f"- {line}")
    return "\n".join(lines)


def _build_history_message(state: dict) -> str:
    """构建 /history 信息（Markdown 格式）。"""
    lines = ["# 当前会话状态"]
    ch = state.get("conversation_history", "")
    eh = state.get("execution_history", "")
    cd = state.get("current_dialogue", [])
    cd_text = dialogue_to_text(cd) if cd else "(空)"
    lines.append(f"\n## 对话历史\n\n{ch if ch else '(空)'}")
    lines.append(f"\n## 执行历史\n\n{eh if eh else '(空)'}")
    lines.append(f"\n## 当前对话\n\n{cd_text}")
    return "\n".join(lines)
