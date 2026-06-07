"""运行时全局配置管理。

模块级 RUNTIME_CONFIG dict 存储可修改的配置项，
通过 /config 命令在 REPL 运行时修改，自动持久化到 user/config/user_config.json，
重启后自动恢复上次保存的值。
"""

import json
import os

# ── 默认值 ──────────────────────────────────────────────
_DEFAULTS = {
    "auto_compact_threshold": 4096,
    "stream_buffer_interval": 2,
    "input_max_lines": 10,
    "tts_enabled": True,
    "tts_voice": "zh-CN-XiaoxiaoNeural",
    "tts_rate": "+0%",
}

RUNTIME_CONFIG = dict(_DEFAULTS)

# ── 持久化路径（基于 config_manager.py 位置解析项目根目录）──
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_USER_CONFIG_PATH = os.path.join(_PROJECT_ROOT, "user", "config", "user_config.json")


def load_user_config() -> None:
    """从 JSON 文件加载持久化配置。

    若文件不存在或损坏，静默回退到代码默认值（RUNTIME_CONFIG 保持 _DEFAULTS）。
    """
    try:
        if os.path.exists(_USER_CONFIG_PATH):
            with open(_USER_CONFIG_PATH, 'r', encoding='utf-8') as f:
                data = json.load(f)
            for k in _DEFAULTS:
                if k in data:
                    if isinstance(data[k], (int, float, bool)):
                        # 类型强制转换：防止 JSON 将 int 解析为 float
                        RUNTIME_CONFIG[k] = type(_DEFAULTS[k])(data[k])
                    else:
                        RUNTIME_CONFIG[k] = data[k]
    except (json.JSONDecodeError, IOError, OSError, TypeError):
        # 文件损坏或不可读：保持默认值，下次保存时覆盖
        pass


def save_user_config() -> None:
    """将当前 RUNTIME_CONFIG 持久化到 JSON 文件。

    自动创建父目录（若不存在）。写入失败时静默忽略（值仍在内存中生效）。
    """
    try:
        os.makedirs(os.path.dirname(_USER_CONFIG_PATH), exist_ok=True)
        with open(_USER_CONFIG_PATH, 'w', encoding='utf-8') as f:
            json.dump(RUNTIME_CONFIG, f, indent=4, ensure_ascii=False)
    except (IOError, OSError):
        # 写入失败不影响运行时行为
        pass


def get_config() -> dict:
    """返回当前运行时配置的引用。

    调用方可直接读取值，config_picker 通过 apply_config() 修改。
    """
    return RUNTIME_CONFIG


def reset_defaults() -> None:
    """恢复所有配置项为默认值，并持久化。"""
    RUNTIME_CONFIG.update(_DEFAULTS)
    save_user_config()


def apply_config(updates: dict) -> None:
    """批量更新配置项（仅更新已有键），并持久化。"""
    changed = False
    for k in updates:
        if k in RUNTIME_CONFIG and RUNTIME_CONFIG[k] != updates[k]:
            RUNTIME_CONFIG[k] = updates[k]
            changed = True
    if changed:
        save_user_config()


# ── 模块导入时自动加载持久化配置 ──
load_user_config()
