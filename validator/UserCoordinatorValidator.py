"""UserCoordinator Formatter 输出校验器。

校验五字段结构：CHAT_MESSAGE, SOP_ID, CURRENT_ACTION, LONG_TERM_INTENT, IS_EXECUTE
IS_EXECUTE 为总闸：false 时允许渐进式确认（SOP_ID/CURRENT_ACTION 可部分填充），true 时要求全部完备。
"""

import re


def validate_coordinator_output(raw_output: str, valid_sop_ids: set) -> tuple:
    """校验 UserCoordinator Formatter 的输出。

    Args:
        raw_output: Formatter 的原始输出文本。
        valid_sop_ids: 有效的 SOP_ID 集合。

    Returns:
        (is_valid, error_reason, parsed_dict)
        parsed_dict keys: chat_message, sop_id, current_action, long_term_intent, is_execute
    """
    text = raw_output.strip()
    text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = text.strip()

    fields = _parse_fields(text)
    if fields is None:
        return False, "无法解析输出格式，缺少必要字段。需要: CHAT_MESSAGE, SOP_ID, CURRENT_ACTION, LONG_TERM_INTENT, IS_EXECUTE", {}

    chat_message = fields.get("chat_message", "")
    sop_id = fields.get("sop_id", "")
    current_action = fields.get("current_action", "")
    long_term_intent = fields.get("long_term_intent", "")
    is_execute = fields.get("is_execute", "")

    # 1. CHAT_MESSAGE 永远非空非 NONE
    if not chat_message or chat_message.upper() == "NONE":
        return False, "CHAT_MESSAGE 不能为空或 NONE", fields

    # 2. IS_EXECUTE 必须为 true 或 false
    is_execute_lower = is_execute.lower()
    if is_execute_lower not in ("true", "false"):
        return False, f"IS_EXECUTE 必须为 'true' 或 'false'，实际为: '{is_execute}'", fields

    # 3. 根据 IS_EXECUTE 执行不同校验规则
    if is_execute_lower == "true":
        # IS_EXECUTE=true: SOP_ID / CURRENT_ACTION / LONG_TERM_INTENT 全部必须有效
        if not sop_id or sop_id.upper() == "NONE":
            return False, "IS_EXECUTE=true 时 SOP_ID 不能为 NONE", fields
        if sop_id not in valid_sop_ids:
            return False, f"SOP_ID '{sop_id}' 不在有效 SOP 列表中。有效值: {sorted(valid_sop_ids)}", fields
        if not current_action or current_action.upper() == "NONE":
            return False, "IS_EXECUTE=true 时 CURRENT_ACTION 不能为空或 NONE", fields
        if not long_term_intent or long_term_intent.upper() == "NONE":
            return False, "IS_EXECUTE=true 时 LONG_TERM_INTENT 不能为空或 NONE", fields
    else:
        # IS_EXECUTE=false: LONG_TERM_INTENT 必须为 NONE
        if long_term_intent and long_term_intent.upper() != "NONE":
            return False, f"IS_EXECUTE=false 时 LONG_TERM_INTENT 必须为 NONE，实际为: '{long_term_intent}'", fields

        sop_is_none = (not sop_id or sop_id.upper() == "NONE")
        action_is_none = (not current_action or current_action.upper() == "NONE")

        if sop_is_none and not action_is_none:
            return False, "SOP_ID 为 NONE 时 CURRENT_ACTION 也必须为 NONE", fields

        if not sop_is_none and sop_id not in valid_sop_ids:
            return False, f"SOP_ID '{sop_id}' 不在有效 SOP 列表中。有效值: {sorted(valid_sop_ids)}", fields

    return True, "", {
        "chat_message": chat_message,
        "sop_id": sop_id if sop_id.upper() != "NONE" else "",
        "current_action": current_action if current_action.upper() != "NONE" else "",
        "long_term_intent": long_term_intent if long_term_intent.upper() != "NONE" else "",
        "is_execute": is_execute_lower,
    }


def _parse_fields(text: str) -> dict | None:
    """解析五字段格式输出，返回 dict 或 None。"""
    field_patterns = [
        ("chat_message", r'^CHAT_MESSAGE:\s*(.+)'),
        ("sop_id", r'^SOP_ID:\s*(.+)'),
        ("current_action", r'^CURRENT_ACTION:\s*(.+)'),
        ("long_term_intent", r'^LONG_TERM_INTENT:\s*(.+)'),
        ("is_execute", r'^IS_EXECUTE:\s*(.+)'),
    ]

    result = {}
    for key, pattern in field_patterns:
        flags = re.MULTILINE | re.DOTALL if key == "chat_message" else re.MULTILINE
        m = re.search(pattern, text, flags)
        if not m:
            return None
        result[key] = m.group(1).strip()

    # 修正：每个字段的值截断到下一个字段
    field_order = ["CHAT_MESSAGE:", "SOP_ID:", "CURRENT_ACTION:", "LONG_TERM_INTENT:", "IS_EXECUTE:"]
    cleaned = {}
    for i, key in enumerate(["chat_message", "sop_id", "current_action", "long_term_intent", "is_execute"]):
        value = result[key]
        for next_prefix in field_order[i+1:]:
            m = re.search(r'^' + re.escape(next_prefix), value, re.MULTILINE)
            idx = m.start() if m else -1
            if idx != -1:
                value = value[:idx].strip()
                break
        cleaned[key] = value

    return cleaned
