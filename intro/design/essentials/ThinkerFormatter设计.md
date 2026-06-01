# Thinker + Formatter — 双阶段推理与格式防幻觉

## 做了什么

CutinAgent 的全部 4 个 LLM 节点（UserCoordinator、SopExecutionScheduler、TaskCompactor、ChatCompactor）统一采用 Thinker + Formatter 双阶段推理模式，每个节点的实现结构完全一致。

### 温度不对称

`config/model_config.json` 中定义了 5 个 LLM 配置项，全部使用同一个基础模型 `qwen3:4b-instruct_q8_8k`，仅采样参数不同：

| 配置项 | temperature | top_p | top_k | num_predict | 使用者 |
|--------|------------|-------|-------|-------------|--------|
| `user_coordinator_thinker` | 0.4 | 0.9 | 20 | 4096 | UserCoordinator Thinker |
| `compactor_thinker` | 0.4 | 0.9 | 20 | 4096 | TaskCompactor Thinker |
| `chat_compactor_thinker` | 0.4 | 0.9 | 20 | 4096 | ChatCompactor Thinker |
| `sop_execution_scheduler_thinker` | 0.4 | 0.9 | 20 | 4096 | Scheduler Thinker |
| `all_formatter` | 0.0 | 0.1 | 20 | 4096 | **全部 4 个节点的 Formatter** |

四个 Thinker 各有独立的 LLM 实例（相同参数但独立创建），但**所有 Formatter 共享同一个 `all_formatter` 实例**。每个节点在闭包工厂创建时通过 `resources.get_llm()` 获取对应的 LLM 实例——Thinker 用各自的 thinker 配置名，Formatter 统一用 `"all_formatter"`。

### Thinker 阶段（温度 0.4）

Thinker 的职责是**生成自由文本推理链，无任何格式约束**。使用 `temperature=0.4`、`top_p=0.9`——留有适度的随机性以处理复杂场景（模糊的用户意图、多意的 SOP 匹配、需要推理的工具参数选择）。

Prompt 以 Ollama 原生的 `<|im_start|>system/assistant` 格式构建，将节点特定的 Thinker prompt 模板与格式化的输入字符串拼接。Thinker 输出经 `stream_llm()` 流式输出到终端（token 级实时打印），同时返回完整推理链文本和 token 用量。

### Formatter 阶段（温度 0.0）

Formatter 的职责是**从推理链中提取结构化字段，不做任何创造性工作**。配置是 `temperature=0.0`、`top_p=0.1`——在给定相同推理链输入的情况下，输出是严格确定性的。

Formatter 的 prompt 只包含一条指令：从 `THINKING_PROCESS` 中提取指定字段并输出规定格式。Formatter 不重新分析用户输入，不重新思考 SOP 匹配，不做任何 Thinker 已经做过的工作。它的输入是 Thinker 的推理链文本，而非原始用户消息。

### Validator + 重试闭环

Formatter 输出后不直接使用，而是先经过代码 Validator 做规则校验。重试循环最多 3 次，每次失败后将错误原因逐次**追加**到 Formatter prompt 末尾（而非覆盖），让模型看到之前所有失败尝试的反馈，有条件逐步修正。

每个节点有自己的 Validator，返回统一的 `(is_valid, reason, parsed)` 三元组：

| Validator | 校验内容 |
|-----------|---------|
| `UserCoordinatorValidator.validate_coordinator_output()` | 五字段是否存在、IS_EXECUTE 规则、SOP_ID 白名单、字段联动 |
| `SopExecutionSchedulerValidator.validate_scheduler_output()` | NEXT_STEP/TOOL_CALL/TASK_STATUS 三元组、工具 ID 白名单、并行 `|` 格式、空字符串参数过滤 |
| `CompactorValidator.validate_compactor_output()` | EVALUATION/CONVERSATION_SUMMARY/EXECUTION_SUMMARY 三字段非空 |

### Fallback 安全兜底

3 次重试全部失败后，不走异常抛出，而是**返回硬编码的安全默认值**。以 UserCoordinator 为例：`chat_message` 设为友好的抱歉提示，`is_execute` 设为 `"false"`——保证不会在格式错乱时意外进入执行状态。Compactor 的 fallback 使用英文文本，因为 fallback 最终追加到历史摘要中供后续 LLM 处理，英文作为中性标记更易识别。

### 所有 LLM 调用均流式输出

每个 Thinker 和 Formatter 调用都经过 `utils/streaming.py` 的 `stream_llm()` 函数，token 级实时打印到终端。该函数遍历 `ChatOllama.stream()` 返回的块，逐 token 写入标准输出，最后返回累积的完整文本和归一化的 token 使用量（Ollama 原生的 `input_tokens`/`output_tokens`/`total_tokens` 被映射为 `input`/`output`/`total`）。

### 调试日志

每次完整的 Thinker+Formatter 调用后，`log_node_io()` 将所有信息写入按 round 分目录的文本日志文件，记录 Thinker 输入全文、推理链全文、每次 Formatter 尝试的输出和验证结果、Thinker 和每次 Formatter 尝试的 token 用量、总耗时、最终映射到 state 的结果。

---

## 为什么这么做

### 4B 模型的核心弱点是输出格式不稳定

qwen3:4b 同样的 prompt 有时输出 JSON，有时 Markdown，有时自然语言。对 Agent 流水线而言，一次格式错误等于系统崩溃——下游解析器无法处理非预期格式。如果只用一个 LLM 调用同时做推理和格式化，模型在思考过程中可能夹杂格式标记、自然语言旁白、或不符合预期字段的输出。

分成两个调用后：Thinker 生成的自然语言推理链无需格式约束，Formatter 拿到的是压缩后的"思考结果"而非原始用户输入——它的任务从"理解意图 + 输出结构化格式"简化为"从已有推理链提取字段"。对 4B 模型而言，后者少了一个认知步骤，实测 Formatter 零重试、100% 格式准确率。

### 链式思考本身就是幻觉抑制

Thinker Prompt 中的推理步骤（分析输入 → 浏览 SOP 库 → 匹配意图 → 推导字段值）是一种引导式模板。模型沿着它一步步思考，就像人类在白板上推理——想得越细，编造越少。这和 "Let's think step by step" 的原理一致，但被编码为每个节点特定的推理步骤。

正面引导比负面约束有效得多。与其说"不要编造不存在的 SOP ID"，不如说"基于以下 SOP_LIBRARY 描述你能处理的问题"。4B 模型在被告诉该做什么时比被告诉不该做什么时更稳定。

### 温度不对称是关键的差异化设计

**Thinker 需要 0.4**：在某些场景下（用户模糊表述、多个可能匹配的 SOP），Thinker 需要足够灵活性来权衡多种可能。temperature=0.0 会在有歧义时给出过于僵硬的推理。

**Formatter 需要 0.0**：Formatter 不做推理，只做提取。零温度保证对于给定的推理链，输出始终一致。如果 Formatter 也有温度，同一个推理链可能在不同时间输出不同格式——Validator 的规则就无从适应。

top_p 配合温度：Thinker 的 top_p=0.9 保留了长尾可能性以处理边界情况；Formatter 的 top_p=0.1 极端收窄，只保留最高概率 token。

### Validator 作为程序化防线

提示词约束是软性的——它们在概率空间中引导模型但无法保证。Validator 是硬性的——代码验证格式正确性的确定性操作。在 Defender-in-Depth 模型中，Validator 是最后防线：

1. Thinker Prompt（正面引导推理步骤）→ 第一道防线
2. Formatter Prompt（要求输出精确格式）→ 第二道防线
3. Formatter temperature=0.0（消除随机性）→ 第三道防线
4. Validator 规则校验 → **第四道也是最后一道硬防线**

3 次重试是工程化决策：第一次通常就会成功（实测 100%），但保留 3 次余地。重试次数太少（1-2 次），LLM 偶尔的非典型输出没有足够修正机会；太多（5+ 次），浪费计算且大概率反复输出相同的错误格式。

### 重试反馈机制的设计考量

每次重试时，错误信息被**追加**到 prompt 末尾，而非覆盖原 prompt。这意味着模型能看到自己前一次的输出、具体的错误原因（如 "SOP_ID 'FULL_HEALTH_CHECK' 不在有效列表中"），然后针对性修正。比笼统的提示（如"格式错误"）更能帮助模型定位问题。

### 所有 Formatter 共享单一实例的理由

四个 Formatter 使用相同的 `all_formatter`，因为它们做的是**同一件事**：从文本中提取结构化字段。无论是从 UserCoordinator Thinker 提取五字段，还是从 Scheduler Thinker 提取工具调用三元组，还是从 TaskCompactor Thinker 提取三字段，还是从 ChatCompactor Thinker 提取单字段——任务本质都是"读取文本 → 输出字段 → 不加入新信息"。相同的 model、temperature、top_p 适用于所有四个 Formatter。分开配置不会提升准确率，只会增加配置复杂度。

---

## 不这么做会怎样

### 单阶段调用（一个 LLM 同时做推理和格式化）

这是 v0 的做法。模型在推理时——例如"用户想知道系统运行状态...我应该匹配 FULL_SYSTEM_HEALTH_CHECK..."——同时试图输出精确格式的结构化字段。结果是中间推理步骤混入输出字段，下游解析器无法提取。一个解析失败意味着整个流程中断。

### Thinker 和 Formatter 用相同温度

如果都用 temperature=0.0 → Thinker 在歧义场景下给出僵硬的推理（例如在多个 SOP 完全匹配时强行选了第一个）。如果都用 temperature=0.4 → Formatter 相同的推理链在不同时间可能输出不同格式（一次 `IS_EXECUTE: true`，下一次 `IS_EXECUTE: yes`），Validator 校验失败。

### 只有 prompt 约束，无 Validator 校验

只靠 prompt 告诉模型"请按如下格式输出"，不加代码校验。结果是模型不按格式输出时没有纠正机制——格式错误传导到下游导致崩溃。模型输出是概率性的，代码校验是确定性的，两者组合总是比单独依赖 prompt 更可靠。

### 无限重试或无重试

无重试 → 一次偶然的格式异常即整个流程失败。无限重试 → 如果模型持续输出同样的错误格式，系统陷入死循环。3 次是在这两种风险之间的平衡：给模型足够的修正机会，同时有明确的终止条件。

### 重试时不反馈具体错误

只让模型"重试"而不告诉它错在哪 → 模型大概率重复同样的错误格式，因为它不知道问题在哪里。例如，Validator 报告 `SOP_ID 'FULL_HEALTH_CHECK' 不在有效列表中`，而不是笼统说"格式错误"，模型才知道要换一个正确的 SOP_ID 而不是改变字段排列方式。
