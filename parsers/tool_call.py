import re
import json


def _build_tool_signature(row) -> str:
    """从 tools.csv 行构建 Python 函数签名: TOOL_ID(params): \"\"\"param_desc\"\"\" """
    tool_id = row["Tool_ID"]
    args_schema_str = row.get("Args_Schema", "{}")
    param_desc = row.get("param_desc", "")

    try:
        schema = json.loads(args_schema_str)
    except (json.JSONDecodeError, TypeError):
        schema = {}

    if not schema:
        return f'{tool_id}(): """{param_desc}"""'

    params = []
    for name, desc in schema.items():
        desc_lower = desc.lower().strip()
        if desc_lower.startswith("str"):
            ptype = "str"
        elif desc_lower.startswith("int"):
            ptype = "int"
        elif desc_lower.startswith("bool"):
            ptype = "bool"
        else:
            ptype = "str"

        default_match = re.search(r"default\s+([^\s)]+)", desc)
        if default_match:
            default_val = default_match.group(1)
            if ptype == "str" and not (default_val.startswith('"') or default_val.startswith("'")):
                default_val = f'"{default_val}"'
            elif ptype == "bool":
                default_val = default_val.capitalize()
            params.append(f"{name}: {ptype} = {default_val}")
        elif "optional" in desc_lower:
            if ptype == "str":
                params.append(f'{name}: str = ""')
            elif ptype == "int":
                params.append(f"{name}: int = 0")
            elif ptype == "bool":
                params.append(f"{name}: bool = False")
        else:
            params.append(f"{name}: {ptype}")

    sig = f"{tool_id}({', '.join(params)})"
    return f'{sig}: """{param_desc}"""'


def _split_parallel_calls(tool_call_raw: str) -> list[str]:
    """按 ' | ' 分割并行工具调用，忽略引号内的 ' | '。"""
    parts = []
    current = []
    in_single = False
    in_double = False
    i = 0
    while i < len(tool_call_raw):
        ch = tool_call_raw[i]
        if ch == "'" and not in_double:
            in_single = not in_single
            current.append(ch)
        elif ch == '"' and not in_single:
            in_double = not in_double
            current.append(ch)
        elif not in_single and not in_double and tool_call_raw[i:i+3] == ' | ':
            parts.append(''.join(current).strip())
            current = []
            i += 3
            continue
        else:
            current.append(ch)
        i += 1
    remaining = ''.join(current).strip()
    if remaining:
        parts.append(remaining)
    return parts
