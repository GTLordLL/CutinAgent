"""Headless 模式输出格式化（plain text / JSON）。"""

import json
from dataclasses import dataclass, field


@dataclass
class HeadlessRunResult:
    """Headless 执行结果数据结构。"""
    status: str = "success"          # "success" | "error"
    sop_id: str = ""
    task_status: str = ""            # FINISH | ONGOING | ERROR | INTERRUPT
    chat_message: str = ""
    total_rounds: int = 0
    total_duration_s: float = 0.0
    node_outputs: list[dict] = field(default_factory=list)
    compactor_evaluation: str = ""
    compactor_conversation_summary: str = ""
    compactor_execution_summary: str = ""
    variables: dict[str, str] = field(default_factory=dict)
    final_report: str = ""
    session_dir: str = ""
    error: str | None = None
    user_message: str = ""           # 对话模式下的 UserCoordinator 回复


def format_plain(result: HeadlessRunResult) -> str:
    """将 HeadlessRunResult 格式化为人类可读的纯文本。"""
    lines = []
    lines.append("=== CutinAgent Headless ===")

    if result.error:
        lines.append(f"Status: ERROR")
        lines.append(f"Error: {result.error}")
        return "\n".join(lines)

    # 摘要行
    parts = []
    if result.sop_id:
        parts.append(f"SOP: {result.sop_id}")
    parts.append(f"Status: {result.task_status}")
    if result.total_rounds:
        parts.append(f"Rounds: {result.total_rounds}")
    if result.total_duration_s:
        parts.append(f"Duration: {result.total_duration_s:.2f}s")
    lines.append(" | ".join(parts))

    if result.user_message:
        lines.append(f"\n--- Message ---\n{result.user_message}")

    if result.chat_message and result.chat_message != result.user_message:
        lines.append(f"\n--- Agent ---\n{result.chat_message}")

    # 节点输出
    if result.node_outputs:
        lines.append("\n--- Nodes ---")
        for no in result.node_outputs:
            node = no.get("node_name", "?")
            dur = no.get("duration", 0)
            detail = no.get("detail_lines", [])
            detail_str = " | ".join(detail) if detail else "(no output)"
            lines.append(f"[{node}] {dur:.2f}s | {detail_str}")

    # Compactor
    if result.compactor_evaluation:
        lines.append(f"\n--- Compactor ---\n{result.compactor_evaluation}")

    # Final report
    if result.final_report:
        lines.append(f"\n--- Report ---\n{result.final_report}")

    return "\n".join(lines)


def format_json(result: HeadlessRunResult) -> str:
    """将 HeadlessRunResult 格式化为 JSON 字符串。"""
    return json.dumps({
        "status": result.status,
        "sop_id": result.sop_id,
        "task_status": result.task_status,
        "chat_message": result.chat_message,
        "total_rounds": result.total_rounds,
        "total_duration_s": result.total_duration_s,
        "node_outputs": [
            {
                "node": no.get("node_name", ""),
                "duration_s": no.get("duration", 0),
                "detail": "\n".join(no.get("detail_lines", [])),
            }
            for no in result.node_outputs
        ],
        "compactor": {
            "evaluation": result.compactor_evaluation,
            "conversation_summary": result.compactor_conversation_summary,
            "execution_summary": result.compactor_execution_summary,
        },
        "variables": result.variables,
        "final_report": result.final_report,
        "session_dir": result.session_dir,
        "user_message": result.user_message,
        "error": result.error,
    }, ensure_ascii=False, indent=2)
