import json
import os as _os
import uuid
from datetime import datetime
from repl.dialogue_utils import parse_dialogue_text

_PROJECT_ROOT = _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__)))
SESSIONS_DIR = _os.path.join(_PROJECT_ROOT, "user", "sessions")
SESSION_FIELDS = (
    "session_id", "session_name",
    "conversation_history", "execution_history",
    "current_dialogue", "sop_ids",
    "created_at",
)


def _get_sessions_dir() -> str:
    """确保 user/sessions/ 存在并返回路径。"""
    _os.makedirs(SESSIONS_DIR, exist_ok=True)
    return SESSIONS_DIR


def generate_session_id() -> str:
    """生成 12 位 hex 会话 ID。"""
    return uuid.uuid4().hex[:12]


def _load_dialogue(raw) -> list[dict]:
    """加载 current_dialogue，向后兼容旧 str 格式。"""
    if isinstance(raw, list):
        return raw
    if isinstance(raw, str):
        return parse_dialogue_text(raw)
    return []


def create_session_dir(base_dir: str | None = None) -> str:
    """创建会话目录并返回路径。同时确保 user/sessions/ 存在。"""
    if base_dir is None:
        base_dir = _os.path.join(_PROJECT_ROOT, "history")
    _get_sessions_dir()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"{base_dir}/{timestamp}_repl_session"
    _os.makedirs(path, exist_ok=True)
    return path


def save_session(state: dict) -> str | None:
    """保存当前会话到 user/sessions/{session_id}.json。

    提取 SESSION_FIELDS 中的字段，写入 JSON 文件。
    如 session_id 为空则自动生成，session_name 为空则设为 "Unnamed"。
    返回 session_id，失败返回 None。
    """
    try:
        _get_sessions_dir()
        session_id = state.get("session_id", "") or generate_session_id()
        session_name = state.get("session_name", "") or "Unnamed"

        data = {
            "session_id": session_id,
            "session_name": session_name,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "conversation_history": state.get("conversation_history", ""),
            "execution_history": state.get("execution_history", ""),
            "current_dialogue": state.get("current_dialogue", []),
            "sop_ids": state.get("sop_ids", []),
        }

        filepath = f"{SESSIONS_DIR}/{session_id}.json"
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        return session_id
    except Exception:
        return None


def load_session(session_id: str) -> dict | None:
    """从 user/sessions/{session_id}.json 加载会话。

    返回包含会话字段的 dict，文件不存在或损坏返回 None。
    """
    try:
        filepath = f"{SESSIONS_DIR}/{session_id}.json"
        with open(filepath, "r", encoding="utf-8") as f:
            data = json.load(f)

        # 向后兼容：旧会话存储 sop_library_text 而非 sop_ids
        sop_ids = data.get("sop_ids", [])
        if not sop_ids and "sop_library_text" in data:
            sop_ids = []
            for line in data["sop_library_text"].strip().split("\n"):
                if "|" in line:
                    sop_ids.append(line.split("|")[0].strip())

        # 提取恢复所需字段
        return {
            "session_id": data.get("session_id", session_id),
            "session_name": data.get("session_name", ""),
            "created_at": data.get("created_at", ""),
            "conversation_history": data.get("conversation_history", ""),
            "execution_history": data.get("execution_history", ""),
            "current_dialogue": _load_dialogue(data.get("current_dialogue", [])),
            "sop_ids": sop_ids,
        }
    except FileNotFoundError:
        return None
    except json.JSONDecodeError:
        return None
    except Exception:
        return None


def list_sessions() -> list[dict]:
    """列出所有已保存会话，按创建时间降序排列。

    返回 [{"session_id", "session_name", "created_at"}, ...]。
    损坏文件自动跳过。
    """
    _get_sessions_dir()
    sessions = []

    try:
        for fname in sorted(_os.listdir(SESSIONS_DIR), reverse=True):
            if not fname.endswith(".json"):
                continue
            filepath = f"{SESSIONS_DIR}/{fname}"
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    data = json.load(f)
                sessions.append({
                    "session_id": data.get("session_id", fname.replace(".json", "")),
                    "session_name": data.get("session_name", "Unnamed"),
                    "created_at": data.get("created_at", ""),
                })
            except (json.JSONDecodeError, Exception):
                # 跳过损坏文件
                continue
    except FileNotFoundError:
        pass

    # 按 created_at 降序
    sessions.sort(key=lambda s: s.get("created_at", ""), reverse=True)
    return sessions


def delete_session(session_id: str) -> bool:
    """删除指定会话文件。"""
    try:
        filepath = f"{SESSIONS_DIR}/{session_id}.json"
        _os.remove(filepath)
        return True
    except FileNotFoundError:
        return False
    except Exception:
        return False


def write_run_summary(session_dir: str, user_query: str,
                      start_dt: datetime, end_dt: datetime, elapsed: float,
                      node_timings: list, final_task_status: str,
                      total_rounds: int):
    """在会话目录写入 RUN_SUMMARY.txt。"""
    path = f"{session_dir}/RUN_SUMMARY.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{'=' * 60}\n")
        f.write(f"CutinAgent REPL 运行摘要\n")
        f.write(f"{'=' * 60}\n\n")
        f.write(f"用户指令: {user_query}\n")
        f.write(f"会话目录: {session_dir}\n")
        f.write(f"开始时间: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"结束时间: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总耗时: {elapsed:.2f}s\n\n")

        f.write("--- 节点耗时分布 ---\n")
        for node_name, dur in node_timings:
            f.write(f"  {node_name}: {dur:.2f}s\n")

        f.write(f"\n--- 最终状态 ---\n")
        f.write(f"  task_status: {final_task_status}\n")
        f.write(f"  总轮次: {total_rounds}\n")
