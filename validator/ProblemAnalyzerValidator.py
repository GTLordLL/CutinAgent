"""Problem Analyzer Formatter 输出校验器。

校验四字段结构：CURRENT_STATE, CONFIDENCE, TOOL_CALL, MY_UNDERSTANDING

校验规则：
- CURRENT_STATE: 非空，非 None
- CONFIDENCE: 必须为 high / medium / low
- TOOL_CALL: confidence=high 时必须为 None；否则可以为调用或 None
- MY_UNDERSTANDING: confidence=high 时必须为非 None 文本；否则必须为 None
"""

from parsers.analyzer_output import parse_analyzer_output


def validate_analyzer_output(raw_output: str) -> tuple:
    """校验 Problem Analyzer Formatter 的输出。

    Args:
        raw_output: Formatter 的原始输出文本。

    Returns:
        (is_valid, error_reason, parsed_dict)
        parsed_dict keys: current_state, confidence, tool_call, my_understanding
    """
    fields = parse_analyzer_output(raw_output)
    if fields is None:
        return False, "无法解析输出格式，缺少必要字段。需要: CURRENT_STATE, CONFIDENCE, TOOL_CALL, MY_UNDERSTANDING", {}

    current_state = fields.get("current_state", "")
    confidence = fields.get("confidence", "").lower().strip()
    tool_call = fields.get("tool_call", "")
    my_understanding = fields.get("my_understanding", "")

    # 1. CURRENT_STATE 永远非空非 NONE
    if not current_state or current_state.upper() == "NONE":
        return False, "CURRENT_STATE 不能为空或 NONE", fields

    # 2. CONFIDENCE 必须为 high / medium / low
    if confidence not in ("high", "medium", "low"):
        return False, f"CONFIDENCE 必须为 'high'、'medium' 或 'low'，实际为: '{confidence}'", fields

    # 3. 根据 CONFIDENCE 校验 TOOL_CALL 和 MY_UNDERSTANDING
    tool_is_none = (not tool_call or tool_call.strip().upper() == "NONE")
    understanding_is_none = (not my_understanding or my_understanding.strip().upper() == "NONE")

    if confidence == "high":
        # high: TOOL_CALL 必须为 None，MY_UNDERSTANDING 必须非 None
        if not tool_is_none:
            return False, f"CONFIDENCE=high 时 TOOL_CALL 必须为 None，实际为: '{tool_call}'", fields
        if understanding_is_none:
            return False, "CONFIDENCE=high 时 MY_UNDERSTANDING 不能为空或 NONE", fields
    else:
        # medium / low: MY_UNDERSTANDING 必须为 None
        if not understanding_is_none:
            return False, f"CONFIDENCE={confidence} 时 MY_UNDERSTANDING 必须为 None，实际为: '{my_understanding}'", fields

    return True, "", {
        "current_state": current_state,
        "confidence": confidence,
        "tool_call": "" if tool_is_none else tool_call,
        "my_understanding": "" if understanding_is_none else my_understanding,
    }
