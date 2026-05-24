def create_initial_state(user_query: str, session_dir: str,
                           sop_library_text: str) -> dict:
    """创建初始 state，包含所有 REPL 键。"""
    return {
        "user_instruction": user_query,
        "session_dir": session_dir,
        "sop_library_text": sop_library_text,

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
        "tool_conclusion": "",
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
        "current_dialogue": "",
        "chat_message": "",
        "current_action": "",
        "long_term_intent": "",
        "is_execute": "false",
        "compactor_evaluation": "",
        "compactor_conversation_summary": "",
        "compactor_execution_summary": "",
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
        "tool_conclusion": "",
        "tool_summary": "",
        "tool_detail_var": "",
        "last_step": "",
        "task_status": "ONGOING",
        "current_round": 0,
        "retry_limit": 3,
        "final_report": "",
        # 重置 UserCoordinator / Compactor 输出
        "chat_message": "",
        "current_action": "",
        "long_term_intent": "",
        "is_execute": "false",
        "compactor_evaluation": "",
        "compactor_conversation_summary": "",
        "compactor_execution_summary": "",
    })
    return state
