"""REPL 按键绑定集中管理。

将 main.py 中散布的 9 个按键绑定（Enter/Ctrl-C/Esc + picker 6 个）
集中到 create_keybindings() 工厂函数。
"""

from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.filters import has_focus
from utils.cancel_token import request_cancel
from repl.pickers.session_picker import (
    picker_select, picker_cancel,
    picker_move_up, picker_move_down,
    picker_page_left, picker_page_right,
)
from repl.pickers.sop_picker import (
    sop_picker_enter, sop_picker_cancel,
    sop_picker_move_up, sop_picker_move_down,
    sop_picker_page_left, sop_picker_page_right,
)
from repl.pickers.config_picker import (
    config_picker_enter, config_picker_cancel,
    config_picker_move_up, config_picker_move_down,
    config_picker_adjust,
)


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


def _register_picker_keybindings(kb, input_field, picker_filter, picker_state, actions: dict):
    """注册 6 个通用 picker 按键绑定 (enter/escape/up/down/left/right)。

    3 组 picker（会话/SOP/设置）共享同一套按键模式，仅 actions 回调不同。

    Args:
        kb: KeyBindings 对象
        input_field: TextArea 输入控件
        picker_filter: 该 picker 激活时的 Condition 过滤器
        picker_state: Picker 状态 dict
        actions: dict，键 "enter"/"escape"/"up"/"down"/"left"/"right"
                 每个值为 callable(picker_state) -> None
                 "left"/"right" 可为 None（跳过注册）
    """
    @kb.add("enter", filter=picker_filter & has_focus(input_field))
    def _on_enter(event):
        input_field.buffer.text = ""
        actions["enter"](picker_state)
        event.app.invalidate()

    @kb.add("escape", filter=picker_filter & has_focus(input_field))
    def _on_escape(event):
        actions["escape"](picker_state)
        event.app.invalidate()

    @kb.add("up", filter=picker_filter)
    def _on_up(event):
        actions["up"](picker_state)
        event.app.invalidate()

    @kb.add("down", filter=picker_filter)
    def _on_down(event):
        actions["down"](picker_state)
        event.app.invalidate()

    if actions.get("left"):
        @kb.add("left", filter=picker_filter)
        def _on_left(event):
            actions["left"](picker_state)
            event.app.invalidate()

    if actions.get("right"):
        @kb.add("right", filter=picker_filter)
        def _on_right(event):
            actions["right"](picker_state)
            event.app.invalidate()


def _register_enter_keybinding(
    kb, input_field, flags, confirm_event, confirm_value, handle_input_coro
) -> None:
    """注册正常 Enter 键：确认等待 / 提交用户输入。"""

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


def _register_command_hint_keybindings(
    kb, input_field, command_hint_state, command_hint_filter
) -> None:
    """注册命令提示的 4 个按键绑定 (up/down/escape/tab)。"""
    from repl.ui.command_hint import (
        command_hint_move_up, command_hint_move_down,
        command_hint_dismiss, command_hint_complete,
    )

    @kb.add("up", filter=command_hint_filter)
    def _on_cmd_hint_up(event):
        command_hint_move_up(command_hint_state)
        event.app.invalidate()

    @kb.add("down", filter=command_hint_filter)
    def _on_cmd_hint_down(event):
        command_hint_move_down(command_hint_state)
        event.app.invalidate()

    @kb.add("escape", filter=command_hint_filter & has_focus(input_field))
    def _on_cmd_hint_escape(event):
        command_hint_dismiss(command_hint_state)
        event.app.invalidate()

    @kb.add("tab", filter=command_hint_filter & has_focus(input_field))
    def _on_cmd_hint_tab(event):
        command_hint_complete(command_hint_state, input_field)
        event.app.invalidate()


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
    command_hint_state: dict = None,
    command_hint_filter=None,
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
        command_hint_state: 命令提示状态 dict（可选）
        command_hint_filter: 命令提示激活时的 Condition 过滤器（可选）
        handle_input_coro: async 回调，接收用户输入文本，签名 (text: str) -> awaitable

    Returns:
        prompt_toolkit KeyBindings 对象
    """
    kb = KeyBindings()

    # ── 正常 Enter：提交用户输入 ──
    _register_enter_keybinding(
        kb, input_field, flags, confirm_event, confirm_value, handle_input_coro
    )

    # ── Escape Enter：插入换行（multiline 模式下手动换行，替代不可检测的 Shift+Enter）──
    @kb.add("escape", "enter", filter=has_focus(input_field))
    def _on_escape_enter(event):
        input_field.buffer.insert_text("\n")

    # ── Ctrl-C：处理中取消任务，空闲时退出 Application ──
    @kb.add("c-c")
    def _on_ctrl_c(event):
        if flags.get("processing"):
            request_cancel()
            if flags.get("waiting_confirm"):
                confirm_event.set()
        else:
            event.app.exit(result="exit")

    # ── Esc：处理中取消任务，空闲时清空输入区 ──
    @kb.add("escape", filter=has_focus(input_field))
    def _on_escape(event):
        if flags.get("processing"):
            request_cancel()
            if flags.get("waiting_confirm"):
                confirm_event.set()
        else:
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
    if command_hint_filter is not None:
        _hist_filter = _hist_filter & ~command_hint_filter

    @kb.add("up", filter=_hist_filter)
    def _on_history_up(event):
        _navigate_history(input_field, direction="up")

    @kb.add("down", filter=_hist_filter)
    def _on_history_down(event):
        _navigate_history(input_field, direction="down")

    # ── 会话选择器按键 ──
    _register_picker_keybindings(kb, input_field, picker_filter, picker_state, {
        "enter": picker_select,
        "escape": picker_cancel,
        "up": picker_move_up,
        "down": picker_move_down,
        "left": picker_page_left,
        "right": picker_page_right,
    })

    # ── SOP 选择器按键 ──
    if sop_picker_state is not None and sop_picker_filter is not None:
        _register_picker_keybindings(kb, input_field, sop_picker_filter, sop_picker_state, {
            "enter": sop_picker_enter,
            "escape": sop_picker_cancel,
            "up": sop_picker_move_up,
            "down": sop_picker_move_down,
            "left": sop_picker_page_left,
            "right": sop_picker_page_right,
        })

    # ── 全局设置选择器按键 ──
    if config_picker_state is not None and config_picker_filter is not None:
        _register_picker_keybindings(kb, input_field, config_picker_filter, config_picker_state, {
            "enter": config_picker_enter,
            "escape": config_picker_cancel,
            "up": config_picker_move_up,
            "down": config_picker_move_down,
            "left": lambda s: config_picker_adjust(s, direction="left"),
            "right": lambda s: config_picker_adjust(s, direction="right"),
        })

    # ── 命令提示按键 ──
    if command_hint_state is not None and command_hint_filter is not None:
        _register_command_hint_keybindings(
            kb, input_field, command_hint_state, command_hint_filter
        )

    return kb
