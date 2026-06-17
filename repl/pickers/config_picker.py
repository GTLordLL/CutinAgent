"""全局设置选择器渲染和交互逻辑。

与 sop_picker.py / session_picker.py 架构一致，差异：
- 不是列表选择，而是设置项数值调整
- Left/Right 键调整当前选中设置的值（而非翻页）
- 底部有"保存"和"恢复默认"按钮
- 激活时从 RUNTIME_CONFIG 拷贝 temp_values，取消则丢弃
"""

import asyncio

from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.filters import Condition

from repl.state.config_manager import get_config, apply_config, reset_defaults

CONFIG_PICKER_HEIGHT = 13

# ── 设置项定义 ─────────────────────────────────────────────
SETTINGS = [
    {
        "key": "auto_compact_threshold",
        "label": "自动压缩阈值",
        "unit": "tokens",
        "min": 1024,
        "max": 8192,
        "step": 1024,
    },
    {
        "key": "stream_buffer_interval",
        "label": "流式缓冲间隔",
        "unit": "s",
        "min": 1,
        "max": 60,
        "step": 1,
    },
    {
        "key": "input_max_lines",
        "label": "输入栏最大行数",
        "unit": "行",
        "min": 1,
        "max": 20,
        "step": 1,
    },
    {
        "key": "analyzer_enabled",
        "label": "问题分析员",
        "unit": "",
        "type": "bool",
    },
    {
        "key": "analyzer_max_rounds",
        "label": "分析最大轮数",
        "unit": "轮",
        "min": 1,
        "max": 5,
        "step": 1,
    },
    {
        "key": "tts_enabled",
        "label": "TTS 语音播报",
        "unit": "",          # 布尔型，显示 开启/关闭
        "type": "bool",
    },
    {
        "key": "tts_voice",
        "label": "TTS 语音",
        "unit": "",
        "type": "choices",
        "choices": [
            ("zh-CN-XiaoxiaoNeural", "Xiaoxiao (女)"),
            ("zh-CN-XiaoyiNeural", "Xiaoyi (轻女)"),
            ("zh-CN-YunjianNeural", "Yunjian (男)"),
            ("zh-CN-YunxiNeural", "Yunxi (活男)"),
            ("zh-CN-YunxiaNeural", "Yunxia (温男)"),
            ("zh-CN-YunyangNeural", "Yunyang (稳男)"),
            ("zh-CN-liaoning-XiaobeiNeural", "Xiaobei (东北)"),
            ("zh-CN-shaanxi-XiaoniNeural", "Xiaoni (陕西)"),
        ],
    },
    {
        "key": "tts_rate",
        "label": "TTS 语速",
        "unit": "",
        "min": -50,
        "max": 100,
        "step": 10,
    },
]

BUTTON_SAVE = 8      # 保存按钮在 selected_index 中的位置
BUTTON_RESET = 9     # 恢复默认按钮位置


# ── State ─────────────────────────────────────────────────

def create_config_picker_state() -> dict:
    """创建配置选择器状态 dict。"""
    return {
        "active": False,
        "selected_index": 0,
        "temp_values": {},     # 激活时从 RUNTIME_CONFIG 拷贝
        "result_event": asyncio.Event(),
        "result": {},
    }


def get_config_picker_condition(state: dict) -> Condition:
    """返回 config picker 激活时触发的 Condition 过滤器。"""
    return Condition(lambda: state["active"])


# ── 渲染 ──────────────────────────────────────────────────

def _build_config_picker_text(state: dict) -> str:
    """根据 state 构建配置选择器的格式化文本。

    从 create_config_picker_control 的 _get_text 闭包提取为纯函数，
    便于独立测试渲染逻辑。
    """
    temp = state["temp_values"]
    selected = state["selected_index"]

    # ── 设置项行 ──
    setting_lines = []
    for i, s in enumerate(SETTINGS):
        prefix = " >" if i == selected else "   "
        hint = " ← →" if i == selected else ""
        if s.get("type") == "bool":
            val_display = "开启" if temp.get(s["key"], False) else "关闭"
            setting_lines.append(
                f"{prefix} {s['label']:　<9} {val_display:<5} {s['unit']:<7}{hint}"
            )
        elif s.get("type") == "choices":
            cur_val = temp.get(s["key"], "")
            display = cur_val
            for val, name in s.get("choices", []):
                if val == cur_val:
                    display = name
                    break
            setting_lines.append(
                f"{prefix} {s['label']:　<9} {display:<12} {s['unit']:<7}{hint}"
            )
        else:
            val = temp.get(s["key"], 0)
            setting_lines.append(
                f"{prefix} {s['label']:　<9} {val:>5} {s['unit']:<7}{hint}"
            )

    # ── 按钮行 ──
    save_prefix = " >" if selected == BUTTON_SAVE else "   "
    reset_prefix = " >" if selected == BUTTON_RESET else "   "

    lines = [
        "",
        "  全局设置",
        "",
        *setting_lines,
        "",
        f"{save_prefix} [ 保存 ]      {reset_prefix} [ 恢复默认 ]",
        "",
        "  ↑ ↓ 选择  ← → 调整  Enter 保存  Esc 取消",
    ]
    return "\n".join(lines)


def create_config_picker_control(state: dict) -> FormattedTextControl:
    """创建全局设置渲染控件。"""
    return FormattedTextControl(lambda: _build_config_picker_text(state))


# ── Activate / Deactivate ─────────────────────────────────

def activate_config_picker(state: dict):
    """激活配置选择器，从 RUNTIME_CONFIG 拷贝当前值到 temp_values。"""
    cfg = get_config()
    state["temp_values"] = dict(cfg)
    state["selected_index"] = 0
    state["result"] = {}
    state["result_event"].clear()
    state["active"] = True


def deactivate_config_picker(state: dict) -> dict:
    """关闭配置选择器，返回 result dict。"""
    state["active"] = False
    return state["result"]


# ── 调整辅助函数 ───────────────────────────────────────────

def _toggle_bool(state: dict, key: str, setting: dict) -> None:
    """切换布尔型配置项。"""
    state["temp_values"][key] = not state["temp_values"].get(key, False)


def _cycle_choice(state: dict, key: str, setting: dict, direction: str) -> None:
    """轮换选择型配置项。"""
    choices = setting.get("choices", [])
    if not choices:
        return
    cur_val = state["temp_values"].get(key, "")
    idx = next((i for i, (v, _) in enumerate(choices) if v == cur_val), 0)
    if direction == "right":
        idx = (idx + 1) % len(choices)
    else:
        idx = (idx - 1) % len(choices)
    state["temp_values"][key] = choices[idx][0]


def _adjust_numeric(state: dict, key: str, setting: dict, direction: str) -> None:
    """增减数值型配置项（支持字符串格式如 "+0%"）。"""
    delta = setting["step"] * (-1 if direction == "left" else 1)
    cur_val = state["temp_values"][key]
    # 支持字符串格式值（如 tts_rate 的 "+0%"）
    if isinstance(cur_val, str):
        numeric = int(cur_val.replace("%", ""))
    else:
        numeric = cur_val
    new_val = numeric + delta
    new_val = max(setting["min"], min(setting["max"], new_val))
    # 保持原始格式
    if isinstance(cur_val, str):
        state["temp_values"][key] = f"{new_val:+d}%"
    else:
        state["temp_values"][key] = new_val


# ── Interaction Handlers ───────────────────────────────────

def config_picker_move_up(state: dict):
    """上移选中项。"""
    state["selected_index"] = max(0, state["selected_index"] - 1)


def config_picker_move_down(state: dict):
    """下移选中项。范围：0..BUTTON_RESET。"""
    state["selected_index"] = min(BUTTON_RESET, state["selected_index"] + 1)


def config_picker_adjust(state: dict, direction: str):
    """调整当前选中设置的值。

    Args:
        direction: "left" 减少, "right" 增加
    """
    idx = state["selected_index"]
    if idx < 0 or idx >= len(SETTINGS):
        return  # 不在设置项上（如按钮行），忽略

    setting = SETTINGS[idx]
    key = setting["key"]

    if setting.get("type") == "bool":
        _toggle_bool(state, key, setting)
    elif setting.get("type") == "choices":
        _cycle_choice(state, key, setting, direction)
    else:
        _adjust_numeric(state, key, setting, direction)


def config_picker_enter(state: dict):
    """Enter 键：保存/恢复默认/忽略（设置项上不处理）。"""
    idx = state["selected_index"]

    if idx == BUTTON_SAVE:
        apply_config(state["temp_values"])
        state["result"] = {"action": "save"}
        state["result_event"].set()
    elif idx == BUTTON_RESET:
        reset_defaults()
        # 同步 temp_values 到默认值
        state["temp_values"] = dict(get_config())
        state["result"] = {"action": "reset"}
        state["result_event"].set()


def config_picker_cancel(state: dict):
    """Esc 取消设置（不保存）。"""
    state["result"] = {"action": "cancel"}
    state["result_event"].set()
