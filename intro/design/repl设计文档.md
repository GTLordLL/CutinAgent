================================================================
  CutinAgent REPL 人机协作模式 — 设计文档
================================================================

## 1. REPL 总体架构

CutinAgent 采用双层架构：

  外层 REPL 循环（main.py）
    ├── UserCoordinator  ←→  用户对话 + 渐进式确认
    ├── [IS_EXECUTE Gate]  ←→  条件路由：聊天 or 执行
    ├── SOP 执行图（LangGraph 3节点内循环）
    │     ├── SopExecutionScheduler (LLM)
    │     ├── ToolExecutor (Data)
    │     └── ProgressUpdater (Data)
    ├── TaskCompactor  ←→  执行评价 + 历史压缩（SOP 执行后）
    └── ChatCompactor  ←→  对话上下文压缩（手动 /compact 或 token>4096 自动触发）

  UserCoordinator 和两个 Compactor 不注册为 LangGraph 节点，由 main.py
  REPL 循环直接调用。它们管理"是否执行"和"执行后如何总结"的元决策，
  而 LangGraph 图只负责"如何执行"。

  用户 ──→ UserCoordinator ──→ [IS_EXECUTE?]
                │                    │
                │ false             │ true
                │ (渐进确认)         │
                ▼                    ▼
          显示 CHAT_MESSAGE    加载 SOP → 执行图 → Compactor
                │                    │
                │                    ▼
                │            满意？→ 累积历史 + 清除对话
                │            不满意 → 保留对话，重新调整
                │                    │
                └────────────────────┘
                        ↓
                下一轮 REPL（用户输入）

## 2. UserCoordinator — 人机协作网关

### 2.1 三意图分类

每轮分析 USER_MESSAGE + CURRENT_DIALOGUE + CONVERSATION_HISTORY +
EXECUTION_HISTORY，将用户意图分为三类：

  CHAT      闲聊、问候、能力询问、致谢、列出SOP等
  UNCERTAIN 用户想做某事但缺少具体目标或范围 — 追问澄清
  EXECUTE   明确请求可映射到 SOP 的具体操作

评判规则：每轮独立判断，历史提供上下文但不改变消息性质。
存疑时优先归为 CHAT 或 UNCERTAIN。

### 2.2 三级渐进式确认（EXECUTE 专属）

确认过程跨越多轮对话，CURRENT_DIALOGUE 追踪当前处于哪个阶段：

  Stage 1 — SOP 匹配：
    扫描 SOP_LIBRARY，找到最匹配的 SOP。若无匹配，诚实告知。
    输出 CHAT_MESSAGE 推荐 SOP 并请求确认。
    IS_EXECUTE=false, SOP_ID 填充, CURRENT_ACTION=NONE

  Stage 2 — 行动细化：
    SOP 已确认。确定仍缺失的具体信息（时间范围、目标目录等）。
    利用 CURRENT_DIALOGUE 和 EXECUTION_HISTORY 提供合理默认值。
    输出 CHAT_MESSAGE 呈现具体行动并请求确认。
    IS_EXECUTE=false, SOP_ID 和 CURRENT_ACTION 填充

  Stage 3 — 最终确认：
    SOP 和 CURRENT_ACTION 均已确认。
    输出 LONG_TERM_INTENT：此任务服务于什么更长远目标。
    输出 CHAT_MESSAGE 确认一切就绪。
    IS_EXECUTE=true, 全部五字段填充

### 2.3 五字段输出

  CHAT_MESSAGE      始终非空的对话回复
  SOP_ID            匹配的 SOP 标识符，无则为 NONE
  CURRENT_ACTION    具体行动描述，无则为 NONE
  LONG_TERM_INTENT  长远意图预测，仅 IS_EXECUTE=true 时有效
  IS_EXECUTE        执行总闸："true" = 确认完毕可执行，"false" = 继续对话

### 2.4 IS_EXECUTE 总闸机制

  IS_EXECUTE 是 CHAT 模式与 EXECUTE 模式之间的硬切换开关：

  "false" → 渐进式确认模式：
    - 显示 CHAT_MESSAGE
    - 追加 Agent 消息到 CURRENT_DIALOGUE
    - 继续 REPL 循环，等待用户下一轮输入
    - LONG_TERM_INTENT 必须为 NONE（Validator 强制）

  "true"  → 最终确认模式：
    - 展示确认摘要（SOP_ID / CURRENT_ACTION / LONG_TERM_INTENT）
    - 等待用户最终许可（y/n/补充信息）
    - y → 加载 SOP → 执行 LangGraph 图
    - n/补充 → 重新进入 UserCoordinator
    - LONG_TERM_INTENT 必须非 NONE（Validator 强制）

### 2.5 Validator 校验规则

  IS_EXECUTE="true" 时：
    - CHAT_MESSAGE 非空
    - SOP_ID 非 NONE 且在有效 SOP 列表中
    - CURRENT_ACTION 非空非 NONE
    - LONG_TERM_INTENT 非空非 NONE

  IS_EXECUTE="false" 时：
    - CHAT_MESSAGE 非空
    - LONG_TERM_INTENT 必须为 NONE
    - SOP_ID 为 NONE 时 CURRENT_ACTION 也必须为 NONE
    - SOP_ID 非 NONE 时必须在有效 SOP 列表中

### 2.6 反幻觉设计

  问题根因：Thinker 的 Output Requirement 最初只要求输出意图分类和
  IS_EXECUTE，没有要求输出 CHAT_MESSAGE。Formatter 提取不到内容，
  退而依赖示例模板，导致编造不存在的 SOP 能力。

  修复策略（正面引导，避免"打补丁"式约束）：
    1. Context 从 "You do NOT execute tasks yourself" 改为
       "You are dedicated to helping users solve problems based on
        the existing SOP_LIBRARY"
    2. CHAT 分支："You can explain what problems you can help solve
       based on the available SOPs in SOP_LIBRARY"
    3. 每个意图分支显式要求 "Output CHAT_MESSAGE with ..."
    4. Stage 3 显式要求 "Output LONG_TERM_INTENT"
    5. Output Requirement 第2条："CHAT_MESSAGE: the exact
       conversational response to send to the user"
    6. Validator 做 SOP_ID 白名单校验

## 3. Compactor — 执行评价与历史压缩

CutinAgent 有两个 Compactor，分工管理 4B 模型的 8K 上下文窗口：

| 维度 | **TaskCompactor** | **ChatCompactor** |
|------|-------------------|-------------------|
| **触发时机** | 每次 SOP 执行完成后 | 手动 `/compact` 或 token > 4096 自动触发 |
| **输出字段** | 3 字段：EVALUATION + CONVERSATION_SUMMARY + EXECUTION_SUMMARY | 1 字段：CONVERSATION_SUMMARY |
| **输出写入** | `conversation_history` + `execution_history` | 仅 `conversation_history` |

> 详细论述见 [Compactor设计.md](essentials/Compactor设计.md) 和 [ChatCompactor设计.md](essentials/ChatCompactor设计.md)。

### 3.1 TaskCompactor 职责

  每次 SOP 执行完毕后运行，完成三件事：
    1. 评价：SOP 是否达成了 CURRENT_ACTION 的目标
    2. 压缩对话：从 CURRENT_DIALOGUE 提取关键信息（目标、约束、偏好）
    3. 压缩执行结果：从执行结果提取关键结论和数据

### 3.2 三字段输出

  EVALUATION            1-2句执行评价
  CONVERSATION_SUMMARY  2-4句对话摘要，追加到 CONVERSATION_HISTORY
  EXECUTION_SUMMARY     2-4句执行摘要，追加到 EXECUTION_HISTORY

### 3.3 对话生命周期

  CURRENT_DIALOGUE 累积规则：
    - 每轮 UserCoordinator 后追加 "Agent: {chat_message}"
    - 用户每次输入追加 "User: {user_msg}"
    - 用户拒绝执行时追加 "User (feedback): {feedback_msg}"

  CURRENT_DIALOGUE 清除规则：
    - 仅在 Compactor 完成后 + 用户对执行结果满意时清除
    - 不满意 → 保留对话，用户可继续调整

  CONVERSATION_HISTORY / EXECUTION_HISTORY 累积规则：
    - Compactor 压缩后追加（非覆盖）
    - 作为后续 UserCoordinator 和 Compactor 的上下文输入
    - 实现跨 SOP 周期的长期记忆

## 4. REPL 主循环流程

  while True:
      1. 读取用户输入 → 追加到 CURRENT_DIALOGUE
      2. UserCoordinator 推理 → 更新 state
      3. 显示 CHAT_MESSAGE → 追加到 CURRENT_DIALOGUE
      4. 判断 IS_EXECUTE：
         false → continue（下一轮输入）
         true  → 展示确认摘要 → 等待用户最终许可
               5. 用户确认 y：
                  a. load_sop_markdown() + SopSpecChecker 校验
                  b. _reset_sop_state()：分离 REPL 字段与执行字段
                  c. 运行 SOP 执行图 (app.stream)
                  d. Compactor 评价与压缩
                  e. 用户满意度确认
                  f. 满意 → 累积历史 + 清除对话
                  g. 写 RUN_SUMMARY.txt
               6. 用户拒绝 n/补充 → 重新进入循环

### 4.1 State 管理

  _reset_sop_state() 在 SOP 执行前重置所有执行相关字段，
  保留 REPL 字段（conversation_history, execution_history,
  current_dialogue）。这确保：
    - 前次执行的中间状态不污染新执行
    - REPL 长期记忆（历史摘要）持续累积

  _create_initial_state() 初始化所有字段，包括：
    - 用户输入与会话元数据
    - SOP 匹配/执行/工具调用 字段（初始为空）
    - REPL 状态字段（初始为空）
    - Compactor 输出字段（初始为空）

## 5. 关键设计决策

### 5.1 UserCoordinator 和 Compactor 为何不注册为 LangGraph 节点

  LangGraph 图是"执行机器"——输入 SOP + action，输出结果。
  UserCoordinator 是"决策门卫"——决定是否执行、执行什么。
  Compactor 是"事后整理"——评价结果、压缩历史。

  将它们放在图外的好处：
    - REPL 循环可以直接控制确认流程（展示摘要、等待用户输入 y/n）
    - Compactor 不参与图的流式事件循环，简化日志和状态管理
    - 图的语义更纯粹：只做 SOP 执行，不做元决策

### 5.2 为何 CURRENT_DIALOGUE 在满意后才清除

  不满意时不清除对话，用户可以说"把时间范围改成昨天"而不是
  从头描述整个需求。这让 Compactor 压缩前的原始对话在需要时
  保持可用，支持迭代调整。

### 5.3 4B 小模型的约束与对策

  目标硬件 RTX 3060 6GB 只能用 4B 模型。对策：
    - Thinker (temp 0.4)：给予推理自由度
    - Formatter (temp 0.0)：严格提取，不做创造性工作
    - Validator 白名单校验：SOP_ID 必须在 sops.csv 中
    - Formatter 最多 3 次重试，校验失败信息反馈到 prompt
    - 示例中不能包含不存在的 SOP 能力（模型会复制模板）
    - Thinker prompt 用正面引导而非负面约束（"你能做什么"
      而非"不要编造"）

### 5.4 工具合约

  所有工具返回三字段 dict：
    {"status": "成功|失败",
     "summary": "结论/原因", "detail": "详细数据"}

  detail 非空 → ToolExecutor 存入 VariableStore (VAR_{TOOL_ID})
  后续步骤通过 data=VAR_{TOOL_ID} 引用

  工具内部完成采集-分析-判断，严禁把 raw data 抛给 4B 模型

### 5.5 节点耗时参考（MVP 测试数据）

  38.88s 完成 2 轮 SOP 执行：
    - SopExecutionScheduler: 12.94s + 12.54s + 11.74s
    - ToolExecutor: 0.00s + 1.65s
    - UserCoordinator / Compactor 各约 7s

  瓶颈在 Scheduler（LLM 推理），每次约 12s。
