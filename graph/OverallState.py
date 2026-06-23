from typing import TypedDict


class OverallState(TypedDict):
    # === 用户输入与会话 ===
    user_instruction: str
    session_dir: str
    session_id: str
    session_name: str
    sop_ids: list[str]

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

    # === 工具执行结果三字段 ===
    tool_status: str            # "成功" / "失败"
    tool_summary: str           # 精简结论/摘要
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

    # === Problem Analyzer 输出 (v0.2) ===
    analyzer_current_state: str       # CURRENT_STATE — 已知事实 + 可选未知缺口
    analyzer_confidence: str          # CONFIDENCE — high / medium / low
    analyzer_tool_call: str           # TOOL_CALL — 工具调用字符串或 None
    analyzer_my_understanding: str    # MY_UNDERSTANDING — high时输出意图推断，否则None
    analyzer_rounds_used: int         # 实际使用的工具调用轮数

    # === REPL 循环状态 (UserCoordinator + Compactor) ===
    conversation_history: str       # Compactor 压缩追加的对话历史
    execution_history: str          # Compactor 压缩追加的执行历史
    current_dialogue: list           # 自上次 Compactor 运行以来的消息列表 [{"role":"user"|"agent"|"feedback"|"error", "content":str}]
    chat_message: str               # UserCoordinator 的聊天回复（始终输出）
    tool_call: str                  # UserCoordinator 输出的 TOOL_CALL 字符串（Phase 2 统一调用格式）
    # === ChatCompactor ===
    thinker_input_tokens: int           # UserCoordinator Thinker 输入 token 数（用于自动压缩阈值判断）
    chat_compact_requirement: str       # /compact 携带的用户压缩要求
    chat_conversation_summary: str      # ChatCompactor 输出的对话摘要
