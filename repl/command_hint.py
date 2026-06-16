"""斜杠命令提示渲染和交互逻辑。

当用户在输入区输入 "/" 时，底部显示可用命令列表（含描述）。
支持 ↑↓ 选择、Tab 补全，输入空格或非 "/" 开头时自动消失。

与 session_picker.py / sop_picker.py / config_picker.py 同样的 mutable-dict +
FormattedTextControl + ConditionalContainer 模式，但它是一个 **非模态** 覆盖层——
不需要 asyncio.Event，而是通过 input_field.buffer.text 驱动可见性和过滤。
"""

from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.filters import Condition

# 10 行命令 + 1 标题 + 1 底部提示
COMMAND_HINT_HEIGHT = 12

# 命令描述映射（与 command_handler._build_help_message 保持一致）
_COMMAND_DESCRIPTIONS = {
    "/help":    "显示帮助信息",
    "/sops":    "列出并选择可用 SOP",
    "/history": "显示当前对话与执行历史摘要",
    "/clear":   "保存会话并开始新会话",
    "/compact": "手动压缩对话上下文",
    "/config":  "修改全局运行时设置",
    "/resume":  "打开会话选择器，恢复历史会话",
    "/analyse": "开启/关闭问题分析员模式，自动收集信息辅助诊断",
    "/exit":    "退出 REPL",
    "/quit":    "退出 REPL",
}


def create_command_hint_state() -> dict:
    """创建命令提示状态字典。

    Returns:
        dict: 包含 commands、filtered_commands、selected_index、dismissed 字段。
    """
    return {
        "commands": [],            # 完整命令列表（由 main.py 填入 REPL_COMMANDS）
        "filtered_commands": [],   # 当前匹配的命令（由 _get_text 渲染时计算）
        "selected_index": 0,       # 当前高亮索引
        "dismissed": False,        # Esc 关闭标记，buffer 不再以 / 开头时自动重置
    }


def get_command_hint_condition(state: dict, input_field) -> Condition:
    """返回命令提示可见性的 Condition 过滤器。

    条件：
    1. 未被 Esc 关闭（dismissed=False），或 buffer 已不满足 "/" 前缀条件（自动重置）
    2. buffer 以 "/" 开头
    3. buffer 不含空格（否则用户已进入参数输入阶段）

    Args:
        state: command_hint_state 可变字典
        input_field: prompt_toolkit TextArea 输入控件

    Returns:
        Condition: 满足条件时激活
    """
    def _is_active() -> bool:
        text = input_field.buffer.text

        # Esc 关闭后：等 buffer 不再是 "/" 开头时自动重置 dismissed
        if state.get("dismissed", False):
            if not text or not text.startswith("/"):
                state["dismissed"] = False
            return False

        # 必须以 "/" 开头且不含空格
        if not text.startswith("/"):
            return False
        if " " in text:
            return False
        return True

    return Condition(_is_active)


def create_command_hint_control(state: dict, input_field) -> FormattedTextControl:
    """创建命令提示渲染控件。

    渲染时从 input_field.buffer.text 读取当前输入，实时过滤命令列表，
    并 clamp selected_index 防止越界。

    Args:
        state: command_hint_state 可变字典
        input_field: prompt_toolkit TextArea 输入控件

    Returns:
        FormattedTextControl: 绑定 _get_text 闭包
    """
    def _get_text() -> str:
        text = input_field.buffer.text
        prefix = text[1:] if (text.startswith("/") and len(text) > 1) else ""
        cmds = state.get("commands", [])

        # 实时过滤
        if prefix:
            filtered = [c for c in cmds if c.startswith(text)]
        else:
            filtered = list(cmds)

        state["filtered_commands"] = filtered

        # Clamp selected_index
        max_idx = max(0, len(filtered) - 1)
        if state["selected_index"] > max_idx:
            state["selected_index"] = max_idx
        if state["selected_index"] < 0:
            state["selected_index"] = 0

        # 渲染
        lines = [f"  斜杠命令 (↑↓ 选择  Tab 补全  Esc 关闭)"]
        for i, cmd in enumerate(filtered):
            prefix_mark = " >" if i == state["selected_index"] else "  "
            desc = _COMMAND_DESCRIPTIONS.get(cmd, "")
            lines.append(f"{prefix_mark} {cmd:<14} {desc}")

        # 填充到 COMMAND_HINT_HEIGHT 行
        while len(lines) < COMMAND_HINT_HEIGHT:
            lines.append("")

        return "\n".join(lines)

    return FormattedTextControl(_get_text)


# ── 交互处理函数（无副作用，不调用 app.invalidate()）──

def command_hint_move_up(state: dict) -> None:
    """上移选中项。"""
    state["selected_index"] = max(0, state["selected_index"] - 1)


def command_hint_move_down(state: dict) -> None:
    """下移选中项。"""
    cmds = state.get("filtered_commands", [])
    max_idx = max(0, len(cmds) - 1)
    state["selected_index"] = min(max_idx, state["selected_index"] + 1)


def command_hint_dismiss(state: dict) -> None:
    """Esc 关闭提示。设置 dismissed=True，叠加层隐藏直到 buffer 不再以 / 开头。"""
    state["dismissed"] = True


def command_hint_complete(state: dict, input_field) -> str | None:
    """Tab 补全：用当前高亮命令替换输入区文本。

    Args:
        state: command_hint_state 可变字典
        input_field: prompt_toolkit TextArea 输入控件

    Returns:
        补全后的命令字符串，如果无匹配则返回 None
    """
    cmds = state.get("filtered_commands", [])
    idx = state.get("selected_index", 0)
    if 0 <= idx < len(cmds):
        cmd = cmds[idx]
        input_field.buffer.text = cmd
        input_field.buffer.cursor_position = len(cmd)
        return cmd
    return None
