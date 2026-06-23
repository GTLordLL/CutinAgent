"""UserCoordinator Formatter 输出校验器。

校验二字段结构：CHAT_MESSAGE, TOOL_CALL
TOOL_CALL 为 Python 函数调用语法（SOP_ID(param='value', ...)）或 NONE。
"""

import re

from parsers.tool_call import parse_single_call


def validate_coordinator_output(raw_output: str, valid_sop_ids: set) -> tuple:
    """校验 UserCoordinator Formatter 的输出。

    Args:
        raw_output: Formatter 的原始输出文本。
        valid_sop_ids: 有效的 SOP_ID 集合（用于校验 TOOL_CALL 中的函数名）。

    Returns:
        (is_valid, error_reason, parsed_dict)
        parsed_dict keys: chat_message, tool_call
    """
    text = raw_output.strip()
    text = re.sub(r'^```[a-zA-Z]*\s*', '', text)
    text = re.sub(r'```\s*$', '', text)
    text = text.strip()

    fields = _parse_fields(text)
    if fields is None:
        return False, "无法解析输出格式，缺少必要字段。需要: CHAT_MESSAGE, TOOL_CALL", {}

    chat_message = fields.get("chat_message", "")
    tool_call = fields.get("tool_call", "")

    # 1. CHAT_MESSAGE 永远非空
    if not chat_message:
        return False, "CHAT_MESSAGE 不能为空", fields

    # 2. TOOL_CALL 校验
    tool_call_upper = tool_call.upper()
    if not tool_call or tool_call_upper == "NONE":
        # CHAT / UNCERTAIN / 无匹配 → 合法
        return True, "", {
            "chat_message": chat_message,
            "tool_call": "",
        }

    # 非 NONE → 必须是合法的函数调用语法
    parsed = parse_single_call(tool_call)
    if parsed is None:
        return False, (
            f"TOOL_CALL 语法无效: '{tool_call[:80]}'。"
            f"应为 SOP_ID(param='value', ...) 或 NONE"
        ), fields

    tool_id, _args = parsed
    if tool_id not in valid_sop_ids:
        return False, (
            f"SOP_ID '{tool_id}' 不在有效 SOP 列表中。"
            f"有效值: {sorted(valid_sop_ids)}"
        ), fields

    return True, "", {
        "chat_message": chat_message,
        "tool_call": tool_call,
    }


def _parse_fields(text: str) -> dict | None:
    """解析二字段格式输出，返回 dict 或 None。"""
    # CHAT_MESSAGE: 可能包含换行，直到遇到 TOOL_CALL: 或文本结束
    chat_match = re.search(r'^CHAT_MESSAGE:\s*(.*?)(?=\nTOOL_CALL:|\Z)', text, re.DOTALL | re.MULTILINE)
    if not chat_match:
        return None

    tool_match = re.search(r'^TOOL_CALL:\s*(.+)$', text, re.MULTILINE)
    if not tool_match:
        return None

    return {
        "chat_message": chat_match.group(1).strip(),
        "tool_call": tool_match.group(1).strip(),
    }
