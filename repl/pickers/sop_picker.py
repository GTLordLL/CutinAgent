"""SOP 多选选择器渲染和交互逻辑。

与 session_picker.py 架构一致，差异：
- 多选模式：Enter 切换 [x]/[ ]，而非直接确认
- 底部有"确定"/"取消"按钮
- selected_index 范围覆盖 SOP 项 + 按钮
"""

import asyncio

from prompt_toolkit.layout.controls import FormattedTextControl
from prompt_toolkit.filters import Condition

SOP_PICKER_HEIGHT = 10
SOPS_PER_PAGE = 5


def create_sop_picker_state() -> dict:
    """创建 SOP 选择器状态 dict（与 status_data / picker_state 模式一致）。"""
    return {
        "active": False,
        "sops": [],            # list[dict]: {"sop_id", "description"}
        "page": 0,
        "selected_index": 0,   # 0..n-1=SOP项, n=确定, n+1=取消
        "selected_ids": set(),  # 当前标记为启用的 SOP_ID 集合
        "result_event": asyncio.Event(),
        "result": {},
    }


def get_sop_picker_condition(state: dict) -> Condition:
    """返回 SOP picker 激活时触发的 Condition 过滤器。"""
    return Condition(lambda: state["active"])


def create_sop_picker_control(state: dict) -> FormattedTextControl:
    """创建 SOP 多选列表渲染控件。"""

    def _get_text():
        sops = state["sops"]
        page = state["page"]
        selected = state["selected_index"]
        selected_ids = state["selected_ids"]

        if not sops:
            return "\n\n  (暂无可用 SOP)\n\n\n\n\n\n  Esc 取消"

        total_pages = (len(sops) + SOPS_PER_PAGE - 1) // SOPS_PER_PAGE
        start = page * SOPS_PER_PAGE
        page_sops = sops[start:start + SOPS_PER_PAGE]
        n_items = len(page_sops)

        lines = [f"  SOP 管理 (第 {page + 1}/{total_pages} 页)"]

        for i, sop in enumerate(page_sops):
            checked = "✓" if sop["sop_id"] in selected_ids else " "
            prefix = " >" if i == selected else "  "
            desc = sop.get("description", "")[:50]
            lines.append(f"{prefix} [{checked}] {sop['sop_id']}  |  {desc}")

        # 填充到 SOPS_PER_PAGE 行，保持按钮位置稳定
        for _ in range(n_items, SOPS_PER_PAGE):
            lines.append("")

        # 按钮行：selected==n_items 高亮"确定"
        btn_confirm = " > 确定" if selected == n_items else "   确定"
        lines.append(btn_confirm)

        lines.append("  ← → 翻页  ↑ ↓ 选择  Enter 切换/确认  Esc 取消")
        return "\n".join(lines)

    return FormattedTextControl(_get_text)


def activate_sop_picker(state: dict, sops: list, current_selected_ids: set):
    """激活 SOP 选择器，填入 SOP 列表和当前已选 ID。"""
    state["sops"] = sops
    state["page"] = 0
    state["selected_index"] = 0
    state["selected_ids"] = set(current_selected_ids)  # copy
    state["result"] = {}
    state["result_event"].clear()
    state["active"] = True


def deactivate_sop_picker(state: dict) -> dict:
    """关闭 SOP 选择器，返回 result dict。"""
    state["active"] = False
    return state["result"]


def sop_picker_move_up(state: dict):
    """上移选中项（绕过 SOP 项 + 按钮）。"""
    state["selected_index"] = max(0, state["selected_index"] - 1)


def sop_picker_move_down(state: dict):
    """下移选中项。范围：0 到 n_items+1（SOP 项 + 确定 + 取消）。"""
    start = state["page"] * SOPS_PER_PAGE
    page_sops = state["sops"][start:start + SOPS_PER_PAGE]
    n_items = len(page_sops)
    max_idx = n_items  # 最后一项是"确定"按钮
    state["selected_index"] = min(max_idx, state["selected_index"] + 1)


def sop_picker_page_left(state: dict):
    """翻到上一页。"""
    state["page"] = max(0, state["page"] - 1)
    state["selected_index"] = 0


def sop_picker_page_right(state: dict):
    """翻到下一页。"""
    total_pages = (len(state["sops"]) + SOPS_PER_PAGE - 1) // SOPS_PER_PAGE
    state["page"] = min(total_pages - 1, state["page"] + 1)
    state["selected_index"] = 0


def sop_picker_enter(state: dict):
    """Enter 键：SOP 项→切换；确定→确认保存；取消→取消。"""
    start = state["page"] * SOPS_PER_PAGE
    page_sops = state["sops"][start:start + SOPS_PER_PAGE]
    n_items = len(page_sops)
    idx = state["selected_index"]

    if idx < n_items:
        # 在 SOP 项上：toggle
        sop_id = page_sops[idx]["sop_id"]
        if sop_id in state["selected_ids"]:
            state["selected_ids"].discard(sop_id)
        else:
            state["selected_ids"].add(sop_id)
    elif idx == n_items:
        # 确定按钮
        state["result"] = {
            "action": "confirm",
            "selected_ids": set(state["selected_ids"]),
        }
        state["result_event"].set()


def sop_picker_cancel(state: dict):
    """Esc 取消选择。"""
    state["result"] = {"action": "cancel"}
    state["result_event"].set()
