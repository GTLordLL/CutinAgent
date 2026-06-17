"""current_dialogue 消息列表的工具函数。

current_dialogue 格式: list[dict]
  每个 dict: {"role": "user"|"agent"|"feedback"|"error", "content": str}
"""

ROLE_PREFIX = {
    "user": "User",
    "agent": "Agent",
    "analyzer": "Analyzer",
    "feedback": "User (feedback)",
    "error": "Agent (error)",
}


def dialogue_to_text(messages: list[dict]) -> str:
    """将消息列表转为 LLM prompt 用的纯文本。

    每行格式: RolePrefix: content
    """
    if not messages:
        return ""
    return "\n".join(
        f"{ROLE_PREFIX[m['role']]}: {m['content']}" for m in messages
    )


def parse_dialogue_text(text: str) -> list[dict]:
    """从旧格式纯文本解析为消息列表（向后兼容）。

    旧格式:
        User: hello
        Agent: Hi!
        User (feedback): more info
        Agent (error): something failed

    返回 list[dict]。
    """
    if not text or not text.strip():
        return []

    messages = []
    for line in text.strip().split("\n"):
        line = line.strip()
        if not line:
            continue
        if line.startswith("User (feedback):"):
            messages.append({
                "role": "feedback",
                "content": line[len("User (feedback):"):].strip(),
            })
        elif line.startswith("Analyzer:"):
            messages.append({
                "role": "analyzer",
                "content": line[len("Analyzer:"):].strip(),
            })
        elif line.startswith("Agent (error):"):
            messages.append({
                "role": "error",
                "content": line[len("Agent (error):"):].strip(),
            })
        elif line.startswith("User:"):
            messages.append({
                "role": "user",
                "content": line[len("User:"):].strip(),
            })
        elif line.startswith("Agent:"):
            messages.append({
                "role": "agent",
                "content": line[len("Agent:"):].strip(),
            })
    return messages
