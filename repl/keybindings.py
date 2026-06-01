"""REPL 按键绑定集中管理。

将 main.py 中散布的 9 个按键绑定（Enter/Ctrl-C/Esc + picker 6 个）
集中到 create_keybindings() 工厂函数。
"""

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import has_focus


def create_keybindings(
    input_field,
    flags: dict,
    confirm_event,
    confirm_value: dict,
    picker_state: dict,
    picker_filter,
    handle_input_coro,
) -> KeyBindings:
    """创建 Application 的全局按键绑定。

    Args:
        input_field: TextArea 输入控件
        flags: mutable dict，字段 {"processing": bool, "waiting_confirm": bool}
        confirm_event: asyncio.Event，确认流程中的等待事件
        confirm_value: mutable dict，传递确认流程中的用户输入文本
        picker_state: 会话选择器状态 dict
        picker_filter: picker 激活时的 Condition 过滤器
        handle_input_coro: async 回调，接收用户输入文本，签名 (text: str) -> awaitable

    Returns:
        prompt_toolkit KeyBindings 对象
    """
    kb = KeyBindings()

    # ── 正常 Enter：处理用户输入 ──
    @kb.add("enter", filter=has_focus(input_field))
    def _on_enter(event):
        text = input_field.buffer.text
        input_field.buffer.text = ""

        if flags["waiting_confirm"]:
            confirm_value["text"] = text
            flags["waiting_confirm"] = False
            confirm_event.set()
        elif flags["processing"]:
            pass  # 处理中，忽略输入
        elif text.strip():
            flags["processing"] = True
            event.app.create_background_task(handle_input_coro(text.strip()))

    # ── Ctrl-C：退出 Application ──
    @kb.add("c-c")
    def _on_ctrl_c(event):
        event.app.exit(result="exit")

    # ── Esc：清空输入区 ──
    @kb.add("escape", filter=has_focus(input_field))
    def _on_escape(event):
        input_field.buffer.text = ""

    # ── 会话选择器按键：仅在 picker 激活时生效 ──
    from repl.session_picker import (
        picker_select, picker_cancel,
        picker_move_up, picker_move_down,
        picker_page_left, picker_page_right,
    )

    @kb.add("enter", filter=picker_filter & has_focus(input_field))
    def _on_picker_enter(event):
        input_field.buffer.text = ""
        picker_select(picker_state)
        event.app.invalidate()

    @kb.add("escape", filter=picker_filter & has_focus(input_field))
    def _on_picker_escape(event):
        picker_cancel(picker_state)
        event.app.invalidate()

    @kb.add("up", filter=picker_filter)
    def _on_picker_up(event):
        picker_move_up(picker_state)
        event.app.invalidate()

    @kb.add("down", filter=picker_filter)
    def _on_picker_down(event):
        picker_move_down(picker_state)
        event.app.invalidate()

    @kb.add("left", filter=picker_filter)
    def _on_picker_left(event):
        picker_page_left(picker_state)
        event.app.invalidate()

    @kb.add("right", filter=picker_filter)
    def _on_picker_right(event):
        picker_page_right(picker_state)
        event.app.invalidate()

    return kb
