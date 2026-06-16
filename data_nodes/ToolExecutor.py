import os
import time
import json
from tools.ToolDispatcher import ToolDispatcher
from data_nodes.VariableStore import store as store_variable


def _save_tool_output(fields: dict, session_dir: str, round_num: int,
                      tool_id: str, var_name: str | None, elapsed_ms: float = 0.0):
    """保存工具输出到 round 目录下的 JSON 文件。"""
    if not session_dir:
        return
    output_dir = os.path.join(session_dir, f"round_{round_num}")
    os.makedirs(output_dir, exist_ok=True)

    safe_tool_id = tool_id.replace("/", "_").replace("\\", "_")
    filename = f"{output_dir}/tool_{safe_tool_id}.json"

    record = {
        "status": fields.get("status", ""),
        "conclusion": fields.get("conclusion", ""),
        "summary": fields.get("summary", ""),
        "detail": fields.get("detail", ""),
    }
    if elapsed_ms > 0:
        record["elapsed_ms"] = round(elapsed_ms, 1)
    if fields.get("token_usage"):
        record["token_usage"] = fields["token_usage"]

    with open(filename, "w", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)


def _process_tool_result(fields: dict, session_dir: str, round_num: int,
                         tool_id: str, elapsed_ms: float = 0.0) -> dict:
    """处理工具返回的四字段 dict，存储 detail 为变量，返回 state 更新字段。"""
    detail = fields.get("detail", "")

    var_name = ""
    if detail:
        var_name = store_variable(detail, tool_id)

    _save_tool_output(fields, session_dir, round_num, tool_id, var_name, elapsed_ms)

    # 拼接 execution_result 字符串（向后兼容日志/显示）
    status = fields.get("status", "")
    conclusion = fields.get("conclusion", "")
    summary = fields.get("summary", "")
    execution_result = f"{status} | {conclusion}"
    if summary:
        execution_result += f" | {summary}"

    return {
        "execution_result": execution_result,
        "tool_status": status,
        "tool_conclusion": conclusion,
        "tool_summary": summary,
        "tool_detail_var": var_name,
    }


def tool_executor_node(state: dict) -> dict:
    """LangGraph 节点：接收 tool_call(s)，分发执行。

    支持单调用和并行多调用。
    工具返回四字段 dict，detail 存入 VariableStore，完整输出保存到 history 文件。
    """
    tool_calls = state.get("current_tool_calls", [])
    dispatcher = ToolDispatcher()
    session_dir = state.get("session_dir", "")
    round_num = state.get("current_round", 0)

    if tool_calls:
        results = []
        all_status = []
        all_conclusion = []
        all_summary = []
        all_detail_var = []
        for tc in tool_calls:
            tool_id = tc.get("tool_id", "")
            tool_args = tc.get("args", {})
            dt_start = time.time()
            raw = dispatcher.dispatch(tool_id, tool_args)
            dt_ms = (time.time() - dt_start) * 1000
            processed = _process_tool_result(raw, session_dir, round_num, tool_id,
                                             elapsed_ms=dt_ms)
            results.append(processed["execution_result"])
            all_status.append(processed["tool_status"])
            all_conclusion.append(processed["tool_conclusion"])
            all_summary.append(processed["tool_summary"])
            all_detail_var.append(processed["tool_detail_var"])

        aggregated = "\n".join(results)
        return {
            "execution_result": aggregated,
            "tool_status": " | ".join(all_status),
            "tool_conclusion": " | ".join(all_conclusion),
            "tool_summary": " | ".join(all_summary),
            "tool_detail_var": " | ".join(v for v in all_detail_var if v),
        }

    tool_call = state.get("current_tool_call", "")
    tool_args = state.get("current_tool_args", {})

    # 空工具调用（如 INTERRUPT 恢复时 TOOL_CALL 为 None）：透传 no-op 结果
    if not tool_call or tool_call == "None":
        return {
            "execution_result": "用户已确认继续。",
            "tool_status": "成功",
            "tool_conclusion": "中断已确认，继续执行后续步骤。",
            "tool_summary": "",
            "tool_detail_var": "",
        }

    dt_start = time.time()
    raw = dispatcher.dispatch(tool_call, tool_args)
    dt_ms = (time.time() - dt_start) * 1000
    return _process_tool_result(raw, session_dir, round_num, tool_call,
                                elapsed_ms=dt_ms)
