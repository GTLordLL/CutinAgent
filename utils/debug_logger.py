import os
import json
from datetime import datetime

_session_dir: str = "history"


def set_session_dir(path: str):
    global _session_dir
    _session_dir = path
    os.makedirs(_session_dir, exist_ok=True)


def get_session_dir() -> str:
    return _session_dir


def log_node_io(
    node_name: str,
    round_num: int,
    thinker_input: str,
    reasoning_chain: str,
    formatter_logs: list,
    final_result: dict,
    session_dir: str = "",
    elapsed_seconds: float = 0.0,
    token_usage: dict | None = None,
):
    target_dir = os.path.join(session_dir or _session_dir, f"round_{round_num}")
    os.makedirs(target_dir, exist_ok=True)

    filename = f"{target_dir}/{node_name}.txt"
    mode = 'a' if os.path.exists(filename) else 'w'

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    lines = []
    if mode == 'a':
        lines.append("")
        lines.append(f"{'~'*40}")
        lines.append(f"[追加调用] {timestamp}")
        lines.append(f"{'~'*40}")

    lines.append(f"{'='*60}")
    lines.append(f"Node: {node_name} | Round: {round_num} | Time: {timestamp}")
    lines.append(f"{'='*60}")
    lines.append("")
    lines.append("--- Thinker Input ---")
    lines.append(thinker_input)
    lines.append("")
    lines.append("--- Reasoning Chain ---")
    lines.append(reasoning_chain)
    lines.append("")

    for i, log_entry in enumerate(formatter_logs):
        retry = log_entry.get("retry", i)
        lines.append(f"--- Formatter Output (Try {retry}) ---")
        lines.append(log_entry.get("output", ""))
        if not log_entry.get("valid", True):
            lines.append(
                f"[Validation Failed] Reason: {log_entry.get('reason', 'Unknown')}"
            )
        else:
            lines.append("[Validation Passed]")
        lines.append("")

    if elapsed_seconds > 0 or token_usage:
        lines.append("--- Timing & Tokens ---")
        if elapsed_seconds > 0:
            lines.append(f"  elapsed: {elapsed_seconds:.2f}s")
        if token_usage:
            thinker = token_usage.get("thinker", {})
            if thinker:
                lines.append(
                    f"  thinker: input={thinker.get('input',0)} "
                    f"output={thinker.get('output',0)} "
                    f"total={thinker.get('total',0)}"
                )
            formatter_list = token_usage.get("formatter", [])
            if formatter_list:
                for i, ft in enumerate(formatter_list):
                    lines.append(
                        f"  formatter_try{i}: input={ft.get('input',0)} "
                        f"output={ft.get('output',0)} "
                        f"total={ft.get('total',0)}"
                    )
        lines.append("")

    lines.append("--- Final Result ---")
    for key, value in final_result.items():
        lines.append(f"  {key}: {str(value)}")
    lines.append("")
    lines.append(f"{'='*60}")
    lines.append("END")

    with open(filename, mode, encoding='utf-8') as f:
        f.write('\n'.join(lines))


def log_state_snapshot(state: dict, session_dir: str, node_name: str, round_num: int):
    """将节点输出的 state 快照写入 round 目录下的 JSON 文件。"""
    target_dir = os.path.join(session_dir or _session_dir, f"round_{round_num}")
    os.makedirs(target_dir, exist_ok=True)

    json_path = f"{target_dir}/state_{node_name}.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2, default=str)
