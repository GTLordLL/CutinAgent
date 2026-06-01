"""运行时全局配置管理。

模块级 RUNTIME_CONFIG dict 存储可修改的配置项，
通过 /config 命令在 REPL 运行时修改，重启后恢复默认值。
"""

# ── 默认值（重启后恢复）───────────────────────────────────
_DEFAULTS = {
    "auto_compact_threshold": 4096,
    "stream_buffer_interval": 2,
    "input_max_lines": 10,
}

RUNTIME_CONFIG = dict(_DEFAULTS)


def get_config() -> dict:
    """返回当前运行时配置的引用。

    调用方可直接读取值，config_picker 通过 apply_config() 修改。
    """
    return RUNTIME_CONFIG


def reset_defaults() -> None:
    """恢复所有配置项为默认值。"""
    RUNTIME_CONFIG.update(_DEFAULTS)


def apply_config(updates: dict) -> None:
    """批量更新配置项（仅更新已有键）。"""
    for k in updates:
        if k in RUNTIME_CONFIG:
            RUNTIME_CONFIG[k] = updates[k]
