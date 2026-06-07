"""会话管理操作封装。

将 main.py 中散布的会话操作（脏检查+保存、状态恢复、/clear、/resume）
集中到独立函数，消除重复代码并简化主流程。
"""

import shutil

from repl.session_manager import (
    save_session,
    load_session,
    list_sessions,
    create_session_dir,
    generate_session_id,
)
from repl.session_picker import activate_picker, deactivate_picker
from utils.debug_logger import set_session_dir
from utils.tts_engine import tts_say


# ── 基础操作 ──────────────────────────────────────────────────


def save_current_if_dirty(state: dict, console, label: str = "当前会话") -> str | None:
    """脏检查：三个对话字段任一非空则保存，返回 session_id。

    消除 /clear、/resume(picker)、/resume(direct) 三处重复（~12行×3）。
    """
    if (state.get("conversation_history", "").strip()
            or state.get("execution_history", "").strip()
            or len(state.get("current_dialogue", [])) > 0):
        saved_id = save_session(state)
        if saved_id:
            console.print(f"[dim]{label}已保存: {saved_id}[/dim]")
        return saved_id
    return None


_RESTORE_KEYS = (
    "session_id", "session_name",
    "conversation_history", "execution_history",
    "current_dialogue", "sop_ids",
)


def restore_session_fields(state: dict, loaded: dict, status_data: dict, app) -> None:
    """将加载的会话字段恢复到 state，重置 token 显示。

    消除 /resume 两处重复（~8行×2）。
    """
    for key in _RESTORE_KEYS:
        if key in loaded:
            state[key] = loaded[key]
    state["thinker_input_tokens"] = 0
    status_data["token_info"] = "0 (0.0%) tokens  ".rjust(
        shutil.get_terminal_size().columns
    )
    app.invalidate()


# ── 命令处理器 ────────────────────────────────────────────────


async def handle_new_session(state: dict, status_data: dict, app, console) -> None:
    """处理 /clear 命令：保存旧会话 → 创建新会话 → 重置 state。"""
    save_current_if_dirty(state, console, label="旧会话")

    new_dir = create_session_dir()
    set_session_dir(new_dir)
    new_session_id = generate_session_id()

    state["session_id"] = new_session_id
    state["session_name"] = ""
    state["session_dir"] = new_dir
    state["conversation_history"] = ""
    state["execution_history"] = ""
    state["current_dialogue"] = []
    state["thinker_input_tokens"] = 0

    status_data["token_info"] = "0 (0.0%) tokens  ".rjust(
        shutil.get_terminal_size().columns
    )

    console.print(f"[bold green]新会话已创建[/bold green]")
    tts_say("新会话已创建")
    console.print(f"[dim]会话 ID: {new_session_id}[/dim]")
    console.print(f"[dim]会话目录: {new_dir}[/dim]")
    app.invalidate()


async def handle_show_picker(picker_state: dict, state: dict,
                              status_data: dict, app, console) -> None:
    """处理 /resume（无参数）：保存当前会话 → 打开选择器 → 恢复选中会话。"""
    sessions = list_sessions()
    if not sessions:
        console.print("[dim]没有已保存的会话。使用 /clear 开始新会话。[/dim]")
        return

    save_current_if_dirty(state, console, label="当前会话")

    activate_picker(picker_state, sessions)
    app.invalidate()

    await picker_state["result_event"].wait()
    result = deactivate_picker(picker_state)
    app.invalidate()

    if result.get("action") == "select":
        session_id = result["session_id"]
        loaded = load_session(session_id)
        if loaded:
            restore_session_fields(state, loaded, status_data, app)
            console.print(f"[bold green]会话已恢复: {session_id}[/bold green]")
            tts_say(f"会话已恢复: {loaded.get('session_name', session_id)}")
            console.print(f"[dim]名称: {loaded.get('session_name', 'Unnamed')}[/dim]")
            console.print(f"[dim]创建时间: {loaded.get('created_at', '?')}[/dim]")
        else:
            console.print(f"[bold red]无法加载会话: {session_id}[/bold red]")
    else:
        console.print("[dim]已取消会话选择。[/dim]")


async def handle_load_session(session_id: str, state: dict,
                               status_data: dict, app, console) -> None:
    """处理 /resume <session_id>：保存当前会话 → 直接加载指定会话。"""
    save_current_if_dirty(state, console, label="当前会话")

    loaded = load_session(session_id)
    if loaded:
        restore_session_fields(state, loaded, status_data, app)
        console.print(f"[bold green]会话已恢复: {session_id}[/bold green]")
        tts_say(f"会话已恢复: {loaded.get('session_name', session_id)}")
    else:
        console.print(f"[bold red]会话未找到: {session_id}[/bold red]")
        tts_say(f"会话未找到: {session_id}")


async def handle_show_sop_picker(sop_picker_state: dict, state: dict,
                                  resources, status_data: dict, app, console) -> None:
    """处理 /sops：打开多选 SOP 选择器，确认后更新 state['sop_ids']。"""
    # 从 CSV 构建 SOP 列表
    sops = []
    for _, row in resources.sops_df.iterrows():
        sops.append({
            "sop_id": row["SOP_ID"],
            "objective": row["Objective"],
            "description": row.get("Description", ""),
        })

    current_ids = set(state.get("sop_ids", []))

    from repl.sop_picker import activate_sop_picker, deactivate_sop_picker
    activate_sop_picker(sop_picker_state, sops, current_ids)
    app.invalidate()

    await sop_picker_state["result_event"].wait()
    result = deactivate_sop_picker(sop_picker_state)
    app.invalidate()

    if result.get("action") == "confirm":
        state["sop_ids"] = sorted(result.get("selected_ids", []))
        console.print(f"[bold green]SOP 配置已更新[/bold green]")
        console.print(f"[dim]活跃 SOP: {', '.join(state['sop_ids']) or '(无)'}[/dim]")
        tts_say(f"SOP 配置已更新。活跃SOP: {', '.join(state['sop_ids']) or '(无)'}")
    else:
        console.print("[dim]SOP 配置未更改。[/dim]")
