import re
from parsers.tool_call import _split_parallel_calls


def validate_tool_call(raw_output: str, valid_tool_ids: set) -> tuple:
    """
    验证 Formatter 输出的工具调用字符串。
    期望格式: Tool_ID(param1='val1', param2=123)
    返回: (is_valid, error_reason, {"tool_id": ..., "args": {...}})
    """
    cleaned = raw_output.strip()
    cleaned = re.sub(r'^```[a-z]*\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.replace("#", "").replace("*", "")

    # 匹配 Tool_ID(...) 格式
    match = re.match(r'(\w+)\((.*)\)', cleaned)
    if not match:
        return False, f"无法解析工具调用格式: '{cleaned[:80]}'", {}

    tool_id = match.group(1)
    args_str = match.group(2).strip()

    if tool_id not in valid_tool_ids:
        return False, f"Tool_ID '{tool_id}' 不在允许的工具列表中", {}

    # 解析参数 key='value', key=number, key=VAR_xxx
    # 注意：True/False/None 等 Python 字面量不捕获，让工具默认参数生效
    args = {}
    if args_str:
        arg_pattern = r"(\w+)\s*=\s*(?:'([^']*)'|\"([^\"]*)\"|(\d+(?:\.\d+)?)|(?!True\b|False\b|None\b)([A-Za-z_]\w*))"
        for m in re.finditer(arg_pattern, args_str):
            key = m.group(1)
            if m.group(2) is not None:
                val = m.group(2)  # single-quoted string (may be empty)
            elif m.group(3) is not None:
                val = m.group(3)  # double-quoted string (may be empty)
            elif m.group(4) is not None:
                val = int(m.group(4)) if '.' not in m.group(4) else float(m.group(4))
            elif m.group(5) is not None:
                val = m.group(5)  # bare identifier (VAR_xxx, etc.)
            else:
                continue
            args[key] = val

    # 清洗空字符串参数：qwen3:4b 习惯写出所有参数名（含空值），
    # 去掉空值让工具函数的 Python 默认参数生效
    args = {k: v for k, v in args.items() if v != ""}

    return True, "", {"tool_id": tool_id, "args": args}


def validate_scheduler_output(raw_output: str, valid_tool_ids: set) -> tuple:
    """Validate SOP Execution Scheduler Formatter output.
    Expected: NEXT_STEP / TOOL_CALL / TASK_STATUS triplet.
    TOOL_CALL supports | -separated multiple calls for parallel execution.
    Returns: (is_valid, error_reason, parsed_dict)
    """
    cleaned = raw_output.strip()
    cleaned = re.sub(r'^```[a-z]*\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)
    cleaned = cleaned.replace("#", "").replace("*", "")

    next_step_match = re.search(r'NEXT_STEP:\s*(.+)', cleaned)
    tool_call_match = re.search(r'TOOL_CALL:\s*(.+)', cleaned)
    status_match = re.search(r'TASK_STATUS:\s*(.+)', cleaned)

    if not next_step_match:
        return False, "缺少 NEXT_STEP 字段", {}
    if not tool_call_match:
        return False, "缺少 TOOL_CALL 字段", {}
    if not status_match:
        return False, "缺少 TASK_STATUS 字段", {}

    next_step = next_step_match.group(1).strip()
    tool_call = tool_call_match.group(1).strip()
    task_status = status_match.group(1).strip().upper()

    valid_statuses = {"FINISH", "ONGOING", "ERROR", "INTERRUPT"}
    if task_status not in valid_statuses:
        return False, f"TASK_STATUS '{task_status}' 不在 {valid_statuses} 中", {}

    if tool_call == "None":
        # Terminal state — no tool
        pass
    else:
        for part in _split_parallel_calls(tool_call):
            if not part:
                continue
            tc_valid, tc_reason, _ = validate_tool_call(part, valid_tool_ids)
            if not tc_valid:
                return False, f"TOOL_CALL 格式错误 ({part}): {tc_reason}", {}

    return True, "", {
        "next_step": next_step,
        "tool_call": tool_call,
        "task_status": task_status,
    }
