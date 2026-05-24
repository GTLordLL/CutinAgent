from typing import TypedDict


class OverallState(TypedDict):
    # === 用户输入与会话 ===
    user_instruction: str
    session_dir: str
    sop_library_text: str

    # === SOP 匹配结果 (UserCoordinator 输出) ===
    matched_sop_id: str
    sop_objective: str
    sop_plan_steps: str          # SOP_PLAN 原地编辑，ProgressUpdater 写入进度标记
    sop_exception_handling: str   # 全局异常处理规则，传给 SopExecutionScheduler
    sop_tools_required: str

    # === 工具调用 (SopExecutionScheduler → ToolExecutor) ===
    current_tool_call: str
    current_tool_call_raw: str
    current_tool_args: dict
    current_tool_calls: list   # 并行调用列表: [{tool_id, args}, ...]
    execution_result: str

    # === 工具执行结果四字段 ===
    tool_status: str            # "成功" / "失败"
    tool_conclusion: str        # 结论/原因
    tool_summary: str           # 精简数据
    tool_detail_var: str        # 变量名 VAR_xxx，无 DETAIL 时为空

    # === 进度追踪 (SopExecutionScheduler 判定) ===
    last_step: str               # 上一轮 SopExecutionScheduler 的 NEXT_STEP
    task_status: str             # FINISH | ONGOING | ERROR | INTERRUPT

    # === 重试机制 ===
    retry_limit: int             # SOP 全局重试上限，从 SOP Retry_Limit 字段提取

    # === 循环控制 ===
    current_round: int

    # === 最终输出 ===
    final_report: str

    # === REPL 循环状态 (UserCoordinator + Compactor) ===
    conversation_history: str       # Compactor 压缩追加的对话历史
    execution_history: str          # Compactor 压缩追加的执行历史
    current_dialogue: str           # 自上次 Compactor 运行以来的原始对话
    chat_message: str               # UserCoordinator 的聊天回复（始终输出）
    current_action: str             # UserCoordinator 输出的当前 SOP 执行行动
    long_term_intent: str           # UserCoordinator 输出的长远意图规划
    is_execute: str                  # UserCoordinator 输出的执行闸门："true" 表示确认完毕可执行
    compactor_evaluation: str       # Compactor 对此次执行的评价
    compactor_conversation_summary: str  # Compactor 输出的对话摘要
    compactor_execution_summary: str     # Compactor 输出的执行摘要
