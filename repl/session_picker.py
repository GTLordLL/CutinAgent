"""会话选择器渲染和交互逻辑。

与 main.py 中的 mutable-dict 模式集成，用于 FormattedTextControl。
"""

import asyncio

from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.filters import Condition

PICKER_HEIGHT = 8
SESSIONS_PER_PAGE = 5


def create_picker_state() -> dict:
    """创建选择器状态 dict（与 status_data / top_status_data 模式一致）。"""
    return {
        "active": False,
        "sessions": [],
        "page": 0,
        "selected_index": 0,
        "result_event": asyncio.Event(),
        "result": {},
    }


def get_picker_condition(picker_state: dict) -> Condition:
    """返回 picker 激活时触发的 Condition 过滤器。"""
    return Condition(lambda: picker_state["active"])


def create_picker_control(picker_state: dict) -> FormattedTextControl:
    """创建会话列表渲染控件。"""

    def _get_text():
        sessions = picker_state["sessions"]
        page = picker_state["page"]
        selected = picker_state["selected_index"]

        if not sessions:
            return "\n\n  (暂无已保存的会话)\n\n\n\n  Esc 取消"

        total_pages = (len(sessions) + SESSIONS_PER_PAGE - 1) // SESSIONS_PER_PAGE
        start = page * SESSIONS_PER_PAGE
        page_sessions = sessions[start:start + SESSIONS_PER_PAGE]

        lines = [f"  会话列表 (第 {page + 1}/{total_pages} 页)"]
        for i, sess in enumerate(page_sessions):
            prefix = " >" if i == selected else "  "
            sid_short = sess.get("session_id", "?")[:8]
            name = (sess.get("session_name", "Unnamed") or "Unnamed")[:35]
            created = sess.get("created_at", "")[:16]
            lines.append(f"{prefix} [{sid_short}] {created}  {name}")

        # 填充到 SESSIONS_PER_PAGE 行
        for _ in range(len(page_sessions), SESSIONS_PER_PAGE):
            lines.append("")

        lines.append("  ← → 翻页  ↑ ↓ 选择  Enter 确认  Esc 取消")
        return "\n".join(lines)

    return FormattedTextControl(_get_text)


def activate_picker(picker_state: dict, sessions: list):
    """激活选择器，填入会话列表。"""
    picker_state["sessions"] = sessions
    picker_state["page"] = 0
    picker_state["selected_index"] = 0
    picker_state["result"] = {}
    picker_state["result_event"].clear()
    picker_state["active"] = True


def deactivate_picker(picker_state: dict) -> dict:
    """关闭选择器，返回 result dict。"""
    picker_state["active"] = False
    return picker_state["result"]


def picker_move_up(picker_state: dict):
    """上移选中项。"""
    picker_state["selected_index"] = max(0, picker_state["selected_index"] - 1)


def picker_move_down(picker_state: dict):
    """下移选中项。"""
    start = picker_state["page"] * SESSIONS_PER_PAGE
    page_sessions = picker_state["sessions"][start:start + SESSIONS_PER_PAGE]
    max_idx = max(0, len(page_sessions) - 1)
    picker_state["selected_index"] = min(max_idx, picker_state["selected_index"] + 1)


def picker_page_left(picker_state: dict):
    """翻到上一页。"""
    picker_state["page"] = max(0, picker_state["page"] - 1)
    picker_state["selected_index"] = 0


def picker_page_right(picker_state: dict):
    """翻到下一页。"""
    total_pages = (len(picker_state["sessions"]) + SESSIONS_PER_PAGE - 1) // SESSIONS_PER_PAGE
    picker_state["page"] = min(total_pages - 1, picker_state["page"] + 1)
    picker_state["selected_index"] = 0


def picker_select(picker_state: dict):
    """确认选择当前高亮会话。"""
    start = picker_state["page"] * SESSIONS_PER_PAGE
    page_sessions = picker_state["sessions"][start:start + SESSIONS_PER_PAGE]
    idx = picker_state["selected_index"]
    if 0 <= idx < len(page_sessions):
        picker_state["result"] = {
            "action": "select",
            "session_id": page_sessions[idx]["session_id"],
        }
    else:
        picker_state["result"] = {"action": "cancel"}
    picker_state["result_event"].set()


def picker_cancel(picker_state: dict):
    """取消选择。"""
    picker_state["result"] = {"action": "cancel"}
    picker_state["result_event"].set()
