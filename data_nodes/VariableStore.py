"""变量存储 —— 内存字典存储工具输出的 [DETAIL] 数据，通过变量名引用。

变量名格式: VAR_{TOOL_ID}，重试时自动追加序号 VAR_{TOOL_ID}_2。
"""

_store: dict[str, str] = {}


def store(data: str, tool_id: str) -> str:
    """存入数据，返回变量名。若同一 tool_id 已有变量，自动追加序号。"""
    base = f"VAR_{tool_id}"
    if base not in _store:
        _store[base] = data
        return base
    i = 2
    while f"{base}_{i}" in _store:
        i += 1
    name = f"{base}_{i}"
    _store[name] = data
    return name


def resolve(var_name: str) -> str:
    """按变量名取出数据，不存在返回空字符串。"""
    return _store.get(var_name, "")


def get_all() -> dict[str, str]:
    """返回当前全部变量的浅拷贝。"""
    return dict(_store)


def clear():
    """清空全部变量。"""
    _store.clear()
