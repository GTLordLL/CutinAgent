def create_initial_state(user_query: str, session_dir: str,
                           sop_ids: list[str]) -> dict:
    """创建初始 state，包含所有 REPL 键。"""
    return {
        "user_instruction": user_query,
        "session_dir": session_dir,
        "session_id": "",
        "session_name": "",
        "sop_ids": sop_ids,

        "matched_sop_id": "",
        "sop_objective": "",
        "sop_plan_steps": "",
        "sop_exception_handling": "",
        "sop_tools_required": "",

        "current_tool_call": "",
        "current_tool_call_raw": "",
        "current_tool_args": {},
        "current_tool_calls": [],
        "execution_result": "",

        "tool_status": "",
        "tool_summary": "",
        "tool_detail_var": "",

        "last_step": "",
        "task_status": "ONGOING",

        "current_round": 0,
        "retry_limit": 3,
        "final_report": "",

        # REPL 状态
        "conversation_history": "",
        "execution_history": "",
        "current_dialogue": [],
        "chat_message": "",
        "tool_call": "",
        # Compactor
        "thinker_input_tokens": 0,
        "chat_compact_requirement": "",
        "chat_conversation_summary": "",

        # Problem Analyzer (v0.2)
        "analyzer_current_state": "",
        "analyzer_confidence": "",
        "analyzer_tool_call": "",
        "analyzer_my_understanding": "",
        "analyzer_rounds_used": 0,
    }


def reset_sop_state(state: dict) -> dict:
    """重置 SOP 执行相关字段，保留 REPL 历史。"""
    state.update({
        "matched_sop_id": "",
        "sop_objective": "",
        "sop_plan_steps": "",
        "sop_exception_handling": "",
        "sop_tools_required": "",
        "current_tool_call": "",
        "current_tool_call_raw": "",
        "current_tool_args": {},
        "current_tool_calls": [],
        "execution_result": "",
        "tool_status": "",
        "tool_summary": "",
        "tool_detail_var": "",
        "last_step": "",
        "task_status": "ONGOING",
        "current_round": 0,
        "retry_limit": 3,
        "final_report": "",
        # 重置 UserCoordinator 输出
        "chat_message": "",
        "tool_call": "",
    })
    return state
