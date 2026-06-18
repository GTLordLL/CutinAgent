# Compactor — 执行评价与历史压缩

## TaskCompactor 与 ChatCompactor 的区分

CutinAgent 有两个 Compactor，各司其职：

| 维度 | **TaskCompactor**（本文档主题） | **ChatCompactor** |
|------|-------------------------------|-------------------|
| **触发时机** | 每次 SOP 执行完成后 | 手动 `/compact` 或 token > 4096 自动触发 |
| **压缩对象** | 本次 SOP 执行结果 + 本轮对话 | 当前对话缓冲区（`current_dialogue`） |
| **输出字段** | 3 字段：EVALUATION + CONVERSATION_SUMMARY + EXECUTION_SUMMARY | 1 字段：CONVERSATION_SUMMARY |
| **输入上下文** | 7 项完整上下文快照（含执行结果） | 4 项对话上下文（无执行状态） |
| **Validator** | `CompactorValidator`（三字段校验） | `ChatCompactorValidator`（单字段校验） |
| **输出写入** | `conversation_history` + `execution_history` | 仅 `conversation_history` |

> **两者都是闭包工厂，不注册为 LangGraph 图节点。** 关注的是"跨 SOP 周期"的信息管理，不受图执行循环约束。ChatCompactor 详见 [ChatCompactor设计.md](ChatCompactor设计.md)。

---

## 做了什么

Compactor（即 TaskCompactor，下同）是每次 SOP 执行完毕后运行的 LLM 节点，负责**评价执行结果 + 压缩历史**。它不在 LangGraph 执行图中（不是 `graph/Builder.py` 注册的节点），而是由 `main.py` 的 REPL 循环在 SOP 图执行完成后直接调用。

### 闭包工厂，不注册为图节点

`llm_nodes/CompactorNode.py` 的 `compactor_node(resources)` 返回一个 `compact(state)` 闭包函数，由 `main.py` REPL 循环直接调用，不注册为 LangGraph 节点。这是有意为之的设计：Compactor 关注的是"跨 SOP 周期"的信息（对话质量、长期意图、历史累积），不应受图执行循环（Scheduler → ToolExecutor → ProgressUpdater）的约束。

### 三字段输出

| 字段 | 含义 | 约束 |
|------|------|------|
| `compactor_evaluation` | 1-2 句评价，直接回答"本次执行是否达成了 CURRENT_ACTION 的目标" | 不能为空或 NONE |
| `compactor_conversation_summary` | 2-4 句用户-Agent 对话摘要 | 不能为空或 NONE，提取长期有效信息 |
| `compactor_execution_summary` | 2-4 句 SOP 执行过程摘要 | 不能为空或 NONE，保留关键结论 |

`validator/CompactorValidator.py` 的 `validate_compactor_output()` 校验三项全部非空非 NONE，格式不符合则触发 Formatter 重试（最多 3 次）。

### Thinker 的输入构造

Compactor Thinker 的输入覆盖了完整的上下文快照：`USER_MESSAGE`（用户原始输入）、`CURRENT_DIALOGUE`（本轮对话）、`CONVERSATION_HISTORY`（历史对话摘要）、`CURRENT_ACTION`（本次执行目标）、`LONG_TERM_INTENT`（长期意图）、`LATEST_EXECUTION_RESULT`（本次执行结果）、`EXECUTION_HISTORY`（历史执行摘要）。

其中 `LATEST_EXECUTION_RESULT` 不是原始系统日志，而是从 state 的工具字段和 SOP 计划合成：拼接 `tool_status`、`tool_summary` 和带进度标记的 `sop_plan_steps` 文本，形成一份结构化的执行结果摘要。

### 生命周期由代码管理（而非 LLM）

Compactor 生成的摘要文本存储在 state 字段中，但**何时追加到永久历史、何时清除当前对话——这些决策由 `main.py` 代码做出**。

具体流程：Compactor 运行后将评价展示给用户 → 用户输入 `y`（满意）时，`compactor_conversation_summary` 追加到 `conversation_history`，`compactor_execution_summary` 追加到 `execution_history`，`current_dialogue` 被清空 → 用户输入 `n`（不满意）时，所有历史保持不变，`current_dialogue` 保留，下一轮 UserCoordinator 可以看到完整上下文来调整方向。

### 3 次重试 + 英文 Fallback

与其他 LLM 节点一样的重试模式。3 次重试全失败后的 fallback 是硬编码英文文本（而非中文），因为 fallback 文本最终追加到历史摘要中供后续 LLM 处理，英文在中文对话流中作为一个明显的"异常标记"，使后续 LLM 能识别出这一轮的历史摘要是不完整的。

### 长期记忆累积机制

- `CONVERSATION_HISTORY`：每轮追加 `CONVERSATION_SUMMARY`，串成跨 SOP 周期的"用户意图链"
- `EXECUTION_HISTORY`：每轮追加 `EXECUTION_SUMMARY`，串成"操作历史链"
- `CURRENT_DIALOGUE`：仅在 Compactor 完成后 + 用户满意后清除

两个 HISTORY 字段无限累积（由 Compactor 的摘要压缩管理增长）。下次 UserCoordinator Thinker 读取它们作为长期上下文。

---

## 为什么这么做

### 4B 模型仅 8K 上下文 —— 不压缩必然溢出

qwen3:4b 的上下文窗口被定制扩展为 8K tokens（从默认 2K）。一个典型的 SOP 执行周期中：SOP Plan_Steps 全文约 500-1000 tokens，每轮工具调用结果约 200-500 tokens，CURRENT_DIALOGUE 约 500-2000 tokens，再叠加 HISTORY 累积和 Thinker prompt。3-4 轮 SOP 执行后，总 token 数轻松超过 8K。当上下文溢出时，LangChain/ChatOllama 会截断最早的消息——丢失的不是冗余内容，而是关键的上下文（用户最初的需求、当前执行到哪一步）。

Compactor 将每轮的对话和执行分别压缩为 2-4 句密集摘要（约 100-200 tokens 每个），而非保留完整的原始文本（约 1000-5000 tokens 每个）。8K 窗口可容纳的 SOP 周期数增加了约一个数量级。

### LLM 做摘要（擅长），代码管理生命周期（需要确定性）

文本摘要——从大量对话中提取必要信息——是 LLM 擅长的任务。决定何时追加历史、何时清除对话——这是状态生命周期决策，需要确定性，不应交给概率模型。

如果把生命周期决策也交给 LLM：LLM 可能在用户不满意时就判定"任务完成"并清除对话；用户说"不对，重新来"但对话已被清除，LLM 不知道之前做了什么；历史摘要中可能混入 LLM 对"是否满意"的错误判断。

`input("满意吗?")` 把最终判断权交给用户，代码根据用户输入执行确定性的状态更新——这个机制不会出错。

### Compactor 不在图中是有意为之

Compactor 关注的是"这次执行是否达成了用户的长期意图"——这是一个跨 SOP 周期的评价问题。把它放在 LangGraph 执行循环中意味着每次工具调用后都会触发评价（评价的是单步而非整体），图循环中累积的上下文更多，图执行和"反思"混在一起职责不清。作为 REPL 外层的独立调用，Compactor 只在"一次完整的 SOP 执行"结束后运行一次。

### 英文 Fallback 的设计考量

当 Compactor 的 3 次重试全部失败时，fallback 使用英文而非中文。这背后的考虑是：fallback 文本是供**后续的 LLM 调用**（下一轮的 UserCoordinator Thinker）阅读的，而非直接展示给用户。英文 fallback 标记在中文对话流中作为一个明显的"异常标记"，使 LLM 在后续处理中能够识别出这一轮的历史摘要是不完整的。

---

## 不这么做会怎样

### 不做历史压缩

3-4 轮 SOP 执行后，8K 上下文窗口塞满 → 模型截断最早的消息 → UserCoordinator 丢失用户最初的需求 → 后续 SOP 匹配错误。Scheduler 丢失 SOP 进度标记 → 不知道该执行哪一步 → 任务失败。用户的长期意图链断裂，每一轮都像是从头开始。

### LLM 管理历史生命周期

LLM 判断"满意" → 可能误判。用户在第三轮执行后给了一个模糊的反馈（"嗯，差不多吧"），LLM 可能将其归类为满意并清除对话。但用户实际想说的是"方向对但不完全对，我想调整一个参数"——对话已被清除，调整无法基于之前的上下文。

### Compactor 放在图中作为图节点

如果 Compactor 是图内的一个节点（在 ProgressUpdater 之后、路由之前），那么每次工具调用循环结束后都会触发评价。对于一个 6 步 SOP，Compactor 会被调用 6 次——但大部分调用时任务尚未完成，评价是无意义的。同时每次调用增加 12-25 秒延迟，6 次额外消耗 1-2 分钟。

### 不区分对话摘要和执行摘要

如果将对话和执行混在一起压缩 → 丢失了谁说了什么的边界 → UserCoordinator 读取历史时无法区分"这来自用户的需求"还是"这来自执行结果" → 语义匹配准确率下降。分开压缩保留了信息源标签。
