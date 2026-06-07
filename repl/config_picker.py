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

from repl.config_manager import get_config, apply_config, reset_defaults

CONFIG_PICKER_HEIGHT = 9

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
        "key": "tts_enabled",
        "label": "TTS 语音播报",
        "unit": "",          # 布尔型，显示 开启/关闭
        "type": "bool",
    },
]

BUTTON_SAVE = 4      # 保存按钮在 selected_index 中的位置
BUTTON_RESET = 5     # 恢复默认按钮位置


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


# ── Render ────────────────────────────────────────────────

def create_config_picker_control(state: dict) -> FormattedTextControl:
    """创建全局设置渲染控件。"""

    def _get_text():
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

    return FormattedTextControl(_get_text)


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
        # 布尔型：Left/Right 切换 True/False
        state["temp_values"][key] = not state["temp_values"].get(key, False)
        return

    delta = setting["step"] * (-1 if direction == "left" else 1)
    new_val = state["temp_values"][key] + delta
    new_val = max(setting["min"], min(setting["max"], new_val))
    state["temp_values"][key] = new_val


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
