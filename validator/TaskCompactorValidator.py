"""Compactor Formatter 输出校验器。

校验三字段结构：EVALUATION, CONVERSATION_SUMMARY, EXECUTION_SUMMARY
"""

import re


def validate_compactor_output(raw_output: str) -> tuple:
    """校验 Compactor Formatter 的输出。

    Args:
        raw_output: Formatter 的原始输出文本。

    Returns:
        (is_valid, error_reason, parsed_dict)
        parsed_dict keys: evaluation, conversation_summary, execution_summary
    """
    text = raw_output.strip()
    # 移除 markdown 代码围栏
    text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = text.strip()

    fields = _parse_fields(text)
    if fields is None:
        return False, "无法解析输出格式，缺少必要字段。需要: EVALUATION, CONVERSATION_SUMMARY, EXECUTION_SUMMARY", {}

    evaluation = fields.get("evaluation", "")
    conversation_summary = fields.get("conversation_summary", "")
    execution_summary = fields.get("execution_summary", "")

    # 每个字段都不能为空或 NONE
    for key, value in [("EVALUATION", evaluation), ("CONVERSATION_SUMMARY", conversation_summary), ("EXECUTION_SUMMARY", execution_summary)]:
        if not value or value.upper() == "NONE":
            return False, f"{key} 不能为空或 NONE", fields

    return True, "", {
        "evaluation": evaluation,
        "conversation_summary": conversation_summary,
        "execution_summary": execution_summary,
    }


def _parse_fields(text: str) -> dict | None:
    """解析三字段格式输出，返回 dict 或 None。"""
    field_patterns = [
        ("evaluation", r'EVALUATION:\s*(.+)'),
        ("conversation_summary", r'CONVERSATION_SUMMARY:\s*(.+)'),
        ("execution_summary", r'EXECUTION_SUMMARY:\s*(.+)'),
    ]

    result = {}
    for key, pattern in field_patterns:
        m = re.search(pattern, text, re.DOTALL)
        if not m:
            return None
        result[key] = m.group(1).strip()

    # 修正：每个字段的值截断到下一个字段
    field_order = ["EVALUATION:", "CONVERSATION_SUMMARY:", "EXECUTION_SUMMARY:"]
    cleaned = {}
    for i, key in enumerate(["evaluation", "conversation_summary", "execution_summary"]):
        value = result[key]
        for next_prefix in field_order[i+1:]:
            idx = value.find(next_prefix)
            if idx != -1:
                value = value[:idx].strip()
                break
        cleaned[key] = value

    return cleaned
