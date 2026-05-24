def build_help_message(resources) -> str:
    """构建 /help 信息。"""
    lines = [
        "=" * 50,
        "  CutinAgent REPL 命令列表",
        "=" * 50,
        "",
        "  /help      显示此帮助信息",
        "  /sops      列出所有可用 SOP",
        "  /history   显示当前对话与执行历史摘要",
        "  /clear     清除对话历史",
        "  /exit      退出 REPL",
        "",
        "--- 可用 SOP ---",
    ]
    for line in resources.sop_library_text.strip().split("\n"):
        lines.append(f"  {line}")
    return "\n".join(lines)


def build_history_message(state: dict) -> str:
    """构建 /history 信息。"""
    lines = ["=" * 50, "  当前会话状态", "=" * 50]
    ch = state.get("conversation_history", "")
    eh = state.get("execution_history", "")
    cd = state.get("current_dialogue", "")
    lines.append(f"\n--- 对话历史 ---\n{ch if ch else '(空)'}")
    lines.append(f"\n--- 执行历史 ---\n{eh if eh else '(空)'}")
    lines.append(f"\n--- 当前对话 ---\n{cd if cd else '(空)'}")
    return "\n".join(lines)


def dispatch_repl_command(cmd: str, state: dict, resources) -> tuple:
    """处理 / 前缀命令。返回 (handled, message, should_exit)。"""
    cmd = cmd.strip()
    if not cmd.startswith("/"):
        return False, None, False

    parts = cmd.split(maxsplit=1)
    name = parts[0].lower()

    if name in ("/exit", "/quit"):
        return True, "再见！", True

    if name == "/help":
        return True, build_help_message(resources), False

    if name == "/sops":
        msg = "可用 SOP 列表:\n" + resources.sop_library_text
        return True, msg, False

    if name == "/clear":
        state["conversation_history"] = ""
        state["execution_history"] = ""
        state["current_dialogue"] = ""
        return True, "对话历史已清除。", False

    if name == "/history":
        return True, build_history_message(state), False

    # 未知 / 命令 — 交给 UserCoordinator 当作普通消息
    return False, None, False
