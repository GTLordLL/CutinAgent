# Thinker + Formatter — 双阶段推理与格式防幻觉

## 做了什么

CutinAgent 的全部 3 个 LLM 节点（UserCoordinator、SopExecutionScheduler、Compactor）统一采用双阶段推理模式：

**Thinker（温度 0.4）**：自由文本推理链，无格式约束。模型被引导按步骤思考——分析输入、枚举可能、权衡利弊、得出结论。链式思考本身就是一种幻觉抑制机制：想得越细，编造越少。

**Formatter（温度 0.0）**：从推理链中提取结构化字段，不做创造性工作。例如 Scheduler 的 Formatter 被要求输出严格的 `NEXT_STEP:` / `TOOL_CALL:` / `TASK_STATUS:` 三行格式。零温度保证相同推理链 → 相同结构化输出。

**Validator + 重试闭环**：Formatter 输出后，代码 Validator 做规则/白名单校验——工具 ID 是否在注册表中、步骤编号是否合法、必填字段是否为空。校验失败 → 错误信息反馈给 Formatter → 重试（最多 3 次）→ 3 次仍失败则回退到硬编码安全默认值。

三个节点共享同一个 `all_formatter` LLM 实例（temp=0.0），但各有独立的 Thinker（temp=0.4）。实测结果：Formatter **零重试，100% 格式准确率**。

## 为什么这么做

4B 模型的核心弱点是输出格式不稳定——同样的 prompt 有时输出 JSON，有时 Markdown，有时自然语言。对 Agent 流水线来说，一次格式错误等于系统崩溃。

传统的解决思路是不断加负面约束——"不要编造工具名" "不要跳过步骤" "不要输出无关内容"。这在 4B 模型上不仅无效，反而让 prompt 膨胀、模型困惑。**正面引导**比负面约束有效得多：Thinker prompt 告诉模型"按什么步骤思考"，Formatter prompt 告诉模型"从推理链中提取什么字段"——模型沿着固定轨道走就不容易跑偏。

温度不对称（Thinker 0.4 vs Formatter 0.0）是关键设计。Thinker 需要温度来灵活推理——如果 Thinker 也是 0.0，模型在复杂场景下推理僵化，可能找不到正确的工具或参数。Formatter 需要 0.0 来保证确定性——如果 Formatter 也有温度，同样的推理链可能输出不同格式，Validator 的校验规则就无从适应。

## 不这么做会怎样

单阶段调用（一次 LLM 同时做推理和格式化）→ 模型在思考过程中夹杂格式标记 → 解析失败。只有负面约束无 Validator → 模型不按格式输出时没有纠正机制 → 一次格式错误即流程中断。Thinker 和 Formatter 用相同温度 → 要么推理僵化（temp 过低），要么格式随机（temp 过高）。
