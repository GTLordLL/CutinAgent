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
    sop_summary: str = ""            # SopSummarizer 输出（Phase 3 替代 Compactor）
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

    # Summary（SopSummarizer 替代旧 Compactor）
    summary_text = result.sop_summary
    if summary_text:
        lines.append(f"\n--- Summary ---\n{summary_text}")

    # Final report
    if result.final_report:
        lines.append(f"\n--- Report ---\n{result.final_report}")

    return "\n".join(lines)


def format_json(result: HeadlessRunResult) -> str:
    """默认 JSON 输出 —— 最小化，机器友好。

    成功时仅输出关键结果；错误时自动附带 debug 信息。
    使用 --output json-full 或 -v 获取完整输出。
    """
    return _format_json_minimal(result)


def _format_json_minimal(result: HeadlessRunResult) -> str:
    """最小化 JSON：ok / sop / status / rounds / duration / result + 错误自动展开。"""
    output: dict = {
        "ok": result.status == "success",
        "sop": result.sop_id,
        "status": result.task_status,
        "rounds": result.total_rounds,
        "duration_s": round(result.total_duration_s, 1),
    }

    # 结果文本：优先 sop_summary → final_report → chat_message
    result_text = (
        result.sop_summary
        or result.final_report
        or result.chat_message
    )
    if result_text:
        output["result"] = result_text

    # Path B 对话模式下的 user_message
    if result.user_message:
        output["user_message"] = result.user_message

    # 错误时自动附带调试信息
    if result.status == "error":
        output["error"] = result.error
        if result.node_outputs:
            output["debug_nodes"] = _summarize_nodes(result.node_outputs)
        if result.variables:
            output["debug_variables"] = result.variables
        if result.session_dir:
            output["session_dir"] = result.session_dir

    return json.dumps(output, ensure_ascii=False, indent=2)


def format_json_full(result: HeadlessRunResult) -> str:
    """完整 JSON 输出 —— 含 node_outputs / compactor / variables，用于调试。"""
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
        "sop_summary": result.sop_summary,
        "variables": result.variables,
        "final_report": result.final_report,
        "session_dir": result.session_dir,
        "user_message": result.user_message,
        "error": result.error,
    }, ensure_ascii=False, indent=2)


def _summarize_nodes(node_outputs: list[dict]) -> list[dict]:
    """对 node_outputs 做轻量摘要，去重 progress_updater 的冗余文本。"""
    summarized = []
    for no in node_outputs:
        detail = "\n".join(no.get("detail_lines", []))
        # progress_updater 的 detail 包含全量 plan+history，截断
        if no.get("node_name") == "progress_updater" and len(detail) > 200:
            detail = detail[:200] + "..."
        summarized.append({
            "node": no.get("node_name", ""),
            "duration_s": no.get("duration", 0),
            "detail": detail,
        })
    return summarized
