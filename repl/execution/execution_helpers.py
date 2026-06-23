"""SOP 执行流程的共享辅助函数。

从 execution_controller.py 的 execute_sop_flow (TUI) 和
execute_sop_flow_headless (CLI) 中提取的 4 处重复逻辑。
"""

from datetime import datetime

from utils.sop_loader import load_sop_markdown
from data_nodes.VariableStore import clear as clear_variables
from repl.state.state_manager import reset_sop_state
from repl.state.session_manager import write_run_summary


def detect_interrupt_resume(state: dict) -> bool:
    """检测是否为 INTERRUPT 恢复场景。

    条件：上次任务状态为 INTERRUPT 且 sop_plan_steps 仍保留进度标记。
    """
    prev = state.get("task_status", "")
    return prev == "INTERRUPT" and bool(state.get("sop_plan_steps", "").strip())


def resume_state_fields(
    state: dict,
    saved_action: str,
) -> None:
    """填充 INTERRUPT 恢复所需的 state 字段（原地修改）。"""
    state["user_instruction"] = saved_action
    state["current_round"] = 0


def load_sop_and_init_state(
    state: dict,
    sop_dir: str,
    valid_tool_ids: set,
    saved_sop_id: str,
    saved_action: str,
) -> dict:
    """加载 SOP markdown 并初始化 state 字段。

    返回新的 state dict（已 reset + 填充 SOP 字段）。
    调用方负责处理 ValueError（SOP 加载失败）。

    Args:
        state: 当前 state dict（会被浅拷贝 reset）
        sop_dir: SOP 文件目录
        valid_tool_ids: 合法工具 ID 集合
        saved_sop_id: 匹配的 SOP ID
        saved_action: 用户意图/行动描述
    """
    sop_md = load_sop_markdown(saved_sop_id, sop_dir, valid_tool_ids)
    state = reset_sop_state(state)
    state.update({
        "matched_sop_id": saved_sop_id,
        "sop_objective": sop_md.get("objective", ""),
        "sop_plan_steps": sop_md.get("plan_steps", ""),
        "sop_tools_required": sop_md.get("tools_required", ""),
        "sop_exception_handling": sop_md.get("exception_handling", ""),
        "retry_limit": (
            int(sop_md.get("retry_limit", "3").strip())
            if sop_md.get("retry_limit", "3").strip().isdigit()
            else 3
        ),
        "user_instruction": saved_action,
        "task_status": "ONGOING",
        "current_round": 0,
    })
    return state


def record_execution_summaries(state: dict) -> None:
    """将 SopSummarizer 摘要追加到执行历史（原地修改）。

    只写入 execution_history（conversation_history 由 Compactor 统一管理）。
    current_dialogue 由 Compactor 负责清空，此处不再清除。
    """
    summary = state.get("sop_summary", "")
    if summary:
        sop_label = f"[SOP:{state.get('matched_sop_id', '')}]"
        entry = f"{sop_label} {summary}"
        exec_hist = state.get("execution_history", "")
        state["execution_history"] = exec_hist + "\n" + entry if exec_hist else entry


def write_sop_run_summary(
    session_dir: str,
    user_query: str,
    start_time: float,
    sop_elapsed: float,
    node_timings: dict,
    final_task_status: str,
    total_rounds: int,
) -> None:
    """封装 write_run_summary 调用，统一时间戳计算逻辑。"""
    write_run_summary(
        session_dir=session_dir,
        user_query=user_query,
        start_dt=datetime.fromtimestamp(start_time),
        end_dt=datetime.fromtimestamp(start_time + sop_elapsed),
        elapsed=sop_elapsed,
        node_timings=node_timings,
        final_task_status=final_task_status,
        total_rounds=total_rounds,
    )
