"""ChatCompactor Formatter 输出校验器。

校验单字段结构：CONVERSATION_SUMMARY
"""

import re


def validate_chat_compactor_output(raw_output: str) -> tuple:
    """校验 ChatCompactor Formatter 的输出。

    Args:
        raw_output: Formatter 的原始输出文本。

    Returns:
        (is_valid, error_reason, parsed_dict)
        parsed_dict keys: conversation_summary
    """
    text = raw_output.strip()
    # 移除 markdown 代码围栏
    text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = text.strip()

    # 解析 CONVERSATION_SUMMARY 字段
    m = re.search(r'CONVERSATION_SUMMARY:\s*(.+)', text, re.DOTALL)
    if not m:
        return False, "无法解析输出格式，缺少必要字段。需要: CONVERSATION_SUMMARY", {}

    conversation_summary = m.group(1).strip()

    # 截断：防止字段值穿越到后续标签
    cut_markers = ["CONVERSATION_SUMMARY:"]
    for marker in cut_markers:
        idx = conversation_summary.find(marker)
        if idx != -1:
            conversation_summary = conversation_summary[:idx].strip()
            break

    # 非空 / 非 NONE 检查
    if not conversation_summary or conversation_summary.upper() == "NONE":
        return False, "CONVERSATION_SUMMARY 不能为空或 NONE", {"conversation_summary": conversation_summary}

    return True, "", {
        "conversation_summary": conversation_summary,
    }
