"""REPL 按键绑定集中管理。

将 main.py 中散布的 9 个按键绑定（Enter/Ctrl-C/Esc + picker 6 个）
集中到 create_keybindings() 工厂函数。
"""

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import has_focus


def _get_user_messages(state: dict) -> list[str]:
    """从 current_dialogue 提取用户消息列表（去重，旧→新）。"""
    if state is None:
        return []
    seen = set()
    result = []
    for m in state.get("current_dialogue", []):
        if m.get("role") in ("user", "feedback"):
            content = m.get("content", "")
            if content and content not in seen:
                seen.add(content)
                result.append(content)
    return result


def _navigate_history(textarea, direction: str) -> None:
    """在 current_dialogue 历史中导航（上=更早，下=更新）。

    由 keybindings 中的 up/down 按键调用。
    直接操作 textarea.buffer.text 实现历史切换。
    """
    state = getattr(textarea, '_state', None)
    user_msgs = _get_user_messages(state)
    if not user_msgs:
        return

    idx = getattr(textarea, '_hist_index', None)

    if direction == "up":
        if idx is None:
            # 首次进入历史导航：保存当前输入
            textarea._hist_saved = textarea.buffer.text
            idx = len(user_msgs)

        if idx > 0:
            idx -= 1
            textarea._hist_index = idx
            textarea.buffer.text = user_msgs[idx]
            textarea.buffer.cursor_position = len(textarea.buffer.text)

    elif direction == "down":
        if idx is None:
            return  # 未在导航模式，忽略

        if idx < len(user_msgs) - 1:
            idx += 1
            textarea._hist_index = idx
            textarea.buffer.text = user_msgs[idx]
            textarea.buffer.cursor_position = len(textarea.buffer.text)
        else:
            # 回到最新位置：恢复保存的原始输入
            textarea._hist_index = None
            textarea.buffer.text = getattr(textarea, '_hist_saved', '')
            textarea.buffer.cursor_position = len(textarea.buffer.text)


def create_keybindings(
    input_field,
    flags: dict,
    confirm_event,
    confirm_value: dict,
    picker_state: dict,
    picker_filter,
    sop_picker_state: dict = None,
    sop_picker_filter=None,
    config_picker_state: dict = None,
    config_picker_filter=None,
    handle_input_coro=None,
) -> KeyBindings:
    """创建 Application 的全局按键绑定。

    Args:
        input_field: TextArea 输入控件
        flags: mutable dict，字段 {"processing": bool, "waiting_confirm": bool}
        confirm_event: asyncio.Event，确认流程中的等待事件
        confirm_value: mutable dict，传递确认流程中的用户输入文本
        picker_state: 会话选择器状态 dict
        picker_filter: picker 激活时的 Condition 过滤器
        sop_picker_state: SOP 选择器状态 dict（可选）
        sop_picker_filter: SOP picker 激活时的 Condition 过滤器（可选）
        config_picker_state: 全局设置选择器状态 dict（可选）
        config_picker_filter: config picker 激活时的 Condition 过滤器（可选）
        handle_input_coro: async 回调，接收用户输入文本，签名 (text: str) -> awaitable

    Returns:
        prompt_toolkit KeyBindings 对象
    """
    kb = KeyBindings()

    # ── 正常 Enter：提交用户输入（multiline 下覆盖默认换行行为）──
    @kb.add("enter", filter=has_focus(input_field))
    def _on_enter(event):
        text = input_field.buffer.text
        input_field.buffer.text = ""

        # 重置历史导航状态
        input_field._hist_index = None

        if flags["waiting_confirm"]:
            confirm_value["text"] = text
            flags["waiting_confirm"] = False
            confirm_event.set()
        elif flags["processing"]:
            pass  # 处理中，忽略输入
        elif text.strip():
            flags["processing"] = True
            event.app.create_background_task(handle_input_coro(text.strip()))

    # ── Escape Enter：插入换行（multiline 模式下手动换行，替代不可检测的 Shift+Enter）──
    @kb.add("escape", "enter", filter=has_focus(input_field))
    def _on_escape_enter(event):
        input_field.buffer.insert_text("\n")

    # ── Ctrl-C：退出 Application ──
    @kb.add("c-c")
    def _on_ctrl_c(event):
        event.app.exit(result="exit")

    # ── Esc：清空输入区 ──
    @kb.add("escape", filter=has_focus(input_field))
    def _on_escape(event):
        input_field.buffer.text = ""
        input_field._hist_index = None

    # ── Up/Down：历史输入导航（仅在无 picker 时生效）──
    _hist_filter = has_focus(input_field)
    if picker_filter is not None:
        _hist_filter = _hist_filter & ~picker_filter
    if sop_picker_filter is not None:
        _hist_filter = _hist_filter & ~sop_picker_filter
    if config_picker_filter is not None:
        _hist_filter = _hist_filter & ~config_picker_filter

    @kb.add("up", filter=_hist_filter)
    def _on_history_up(event):
        _navigate_history(input_field, direction="up")

    @kb.add("down", filter=_hist_filter)
    def _on_history_down(event):
        _navigate_history(input_field, direction="down")

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

    # ── SOP 选择器按键：仅在 SOP picker 激活时生效 ──
    if sop_picker_state is not None and sop_picker_filter is not None:
        from repl.sop_picker import (
            sop_picker_enter, sop_picker_cancel,
            sop_picker_move_up, sop_picker_move_down,
            sop_picker_page_left, sop_picker_page_right,
        )

        @kb.add("enter", filter=sop_picker_filter & has_focus(input_field))
        def _on_sop_picker_enter(event):
            input_field.buffer.text = ""
            sop_picker_enter(sop_picker_state)
            event.app.invalidate()

        @kb.add("escape", filter=sop_picker_filter & has_focus(input_field))
        def _on_sop_picker_escape(event):
            sop_picker_cancel(sop_picker_state)
            event.app.invalidate()

        @kb.add("up", filter=sop_picker_filter)
        def _on_sop_picker_up(event):
            sop_picker_move_up(sop_picker_state)
            event.app.invalidate()

        @kb.add("down", filter=sop_picker_filter)
        def _on_sop_picker_down(event):
            sop_picker_move_down(sop_picker_state)
            event.app.invalidate()

        @kb.add("left", filter=sop_picker_filter)
        def _on_sop_picker_left(event):
            sop_picker_page_left(sop_picker_state)
            event.app.invalidate()

        @kb.add("right", filter=sop_picker_filter)
        def _on_sop_picker_right(event):
            sop_picker_page_right(sop_picker_state)
            event.app.invalidate()

    # ── 全局设置选择器按键：仅在 config picker 激活时生效 ──
    if config_picker_state is not None and config_picker_filter is not None:
        from repl.config_picker import (
            config_picker_enter, config_picker_cancel,
            config_picker_move_up, config_picker_move_down,
            config_picker_adjust,
        )

        @kb.add("enter", filter=config_picker_filter & has_focus(input_field))
        def _on_config_picker_enter(event):
            input_field.buffer.text = ""
            config_picker_enter(config_picker_state)
            event.app.invalidate()

        @kb.add("escape", filter=config_picker_filter & has_focus(input_field))
        def _on_config_picker_escape(event):
            config_picker_cancel(config_picker_state)
            event.app.invalidate()

        @kb.add("up", filter=config_picker_filter)
        def _on_config_picker_up(event):
            config_picker_move_up(config_picker_state)
            event.app.invalidate()

        @kb.add("down", filter=config_picker_filter)
        def _on_config_picker_down(event):
            config_picker_move_down(config_picker_state)
            event.app.invalidate()

        @kb.add("left", filter=config_picker_filter)
        def _on_config_picker_left(event):
            config_picker_adjust(config_picker_state, direction="left")
            event.app.invalidate()

        @kb.add("right", filter=config_picker_filter)
        def _on_config_picker_right(event):
            config_picker_adjust(config_picker_state, direction="right")
            event.app.invalidate()

    return kb
