"""Problem Analyzer Formatter 输出解析器。

解析四字段结构：CURRENT_STATE, CONFIDENCE, TOOL_CALL, MY_UNDERSTANDING
复用 UserCoordinatorValidator._parse_fields 的截断逻辑。
"""

import re


def parse_analyzer_output(text: str) -> dict | None:
    """从 Formatter 输出中提取四字段。

    Args:
        text: Formatter 的原始输出文本。

    Returns:
        dict with keys: current_state, confidence, tool_call, my_understanding
        解析失败返回 None。
    """
    text = text.strip()
    text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = text.strip()

    field_patterns = [
        ("current_state", r'^CURRENT_STATE:\s*(.+)'),
        ("confidence", r'^CONFIDENCE:\s*(.+)'),
        ("tool_call", r'^TOOL_CALL:\s*(.+)'),
        ("my_understanding", r'^MY_UNDERSTANDING:\s*(.+)'),
    ]

    result = {}
    for key, pattern in field_patterns:
        flags = re.MULTILINE | re.DOTALL if key in ("current_state", "my_understanding") else re.MULTILINE
        m = re.search(pattern, text, flags)
        if not m:
            return None
        result[key] = m.group(1).strip()

    # 每个字段的值截断到下一个字段
    field_order = ["CURRENT_STATE:", "CONFIDENCE:", "TOOL_CALL:", "MY_UNDERSTANDING:"]
    cleaned = {}
    for i, key in enumerate(["current_state", "confidence", "tool_call", "my_understanding"]):
        value = result[key]
        for next_prefix in field_order[i+1:]:
            m = re.search(r'^' + re.escape(next_prefix), value, re.MULTILINE)
            idx = m.start() if m else -1
            if idx != -1:
                value = value[:idx].strip()
                break
        cleaned[key] = value

    return cleaned
