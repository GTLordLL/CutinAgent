import re
import json


def _build_tool_signature(row) -> str:
    """从 CSV 行构建 Python 函数签名（兼容 tools.csv 和 sops.csv）。

    格式: TOOL_ID(params): \"\"\"func_desc — param_desc\"\"\"
    支持 Tool_ID / SOP_ID 双列名，Func_Desc / param_desc 可选。
    """
    tool_id = row.get("Tool_ID") or row.get("SOP_ID", "")
    func_desc = row.get("Func_Desc", "")
    args_schema_str = row.get("Args_Schema", "{}")
    param_desc = row.get("param_desc", "")

    # 构建 docstring: func_desc — param_desc (任一缺失则省略)
    doc_parts = []
    if func_desc:
        doc_parts.append(func_desc)
    if param_desc:
        doc_parts.append(param_desc)
    doc = " — ".join(doc_parts)

    try:
        schema = json.loads(args_schema_str)
    except (json.JSONDecodeError, TypeError):
        schema = {}

    if not schema:
        return f'{tool_id}(): """{doc}"""'

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
    return f'{sig}: """{doc}"""'


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


def _extract_positional_args(args_str: str) -> list[str]:
    """从函数调用参数字符串中按顺序提取位置参数值。

    支持单引号字符串、双引号字符串、裸数字/标识符。
    引号内逗号和括号不会被当作分隔符。
    """
    result = []
    i = 0
    n = len(args_str)
    while i < n:
        ch = args_str[i]
        if ch in (' ', ','):
            i += 1
            continue
        if ch == "'":
            j = i + 1
            while j < n and args_str[j] != "'":
                if args_str[j] == '\\':
                    j += 1
                j += 1
            result.append(args_str[i + 1:j])
            i = j + 1
            continue
        if ch == '"':
            j = i + 1
            while j < n and args_str[j] != '"':
                if args_str[j] == '\\':
                    j += 1
                j += 1
            result.append(args_str[i + 1:j])
            i = j + 1
            continue
        # 裸值 (数字 / 标识符 / bool)
        j = i
        while j < n and args_str[j] not in (' ', ',', ')'):
            j += 1
        if j > i:
            result.append(args_str[i:j])
            i = j
            continue
        i += 1
    return result


def parse_single_call(call_str: str, param_names: list[str] | None = None) -> tuple | None:
    """Parse a single tool call string into (tool_id, args_dict).

    Handles formats like:
        Tool_ID()                          → ('Tool_ID', {})
        Tool_ID(count=10)                  → ('Tool_ID', {'count': 10})
        Tool_ID(staged='false', base='')   → ('Tool_ID', {'staged': 'false', 'base': ''})

    Positional arguments (without key=) are also supported when param_names
    is provided — they are mapped to param_names by position:
        run_command('git status')          → ('run_command', {'command': 'git status'})

    Returns None if the call string cannot be parsed.
    """
    m = re.match(r'(\w+)\((.*)\)', call_str.strip())
    if not m:
        return None
    tool_id = m.group(1)
    args_str = m.group(2).strip()
    args = {}
    if args_str:
        # Match key=value pairs; value can be single-quoted, double-quoted, or bare
        for kv_match in re.finditer(
            r"(\w+)\s*=\s*(?:'([^']*)'|\"([^\"]*)\"|(\d+(?:\.\d+)?)|((?i:true|false|none)))",
            args_str
        ):
            key = kv_match.group(1)
            if kv_match.group(2) is not None:       # single-quoted
                val = kv_match.group(2)
            elif kv_match.group(3) is not None:     # double-quoted
                val = kv_match.group(3)
            elif kv_match.group(4) is not None:     # numeric — keep as string, tools cast with int()/float() as needed
                val = kv_match.group(4)
            elif kv_match.group(5) is not None:     # True/False/None — keep as string to avoid bool.lower() AttributeError
                val = kv_match.group(5)
            else:
                continue
            args[key] = val

        # Fallback: positional arguments (when no key=value pairs matched)
        if not args and param_names:
            pos_vals = _extract_positional_args(args_str)
            for i, val in enumerate(pos_vals):
                if i < len(param_names):
                    args[param_names[i]] = val

    return tool_id, args
