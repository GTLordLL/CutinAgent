# UserCoordinator — 人机协作网关

## 做了什么

UserCoordinator 是 REPL 外层的 LLM 节点，通过**五字段输出 + IS_EXECUTE 闸门 + 三级渐进确认**，在用户自然语言指令和 SOP 执行引擎之间建立一道可控的安全边界。

### 闭包工厂模式

`llm_nodes/UserCoordinatorNode.py` 的 `user_coordinator_node(resources)` 不是直接执行推理，而是返回一个 `coordinator(state)` 闭包函数。这类似于依赖注入：LLM 实例、prompt 模板、SOP 白名单在工厂创建时注入（一次性），随后每次调用只传入变化的 state。

### 五字段输出

每轮调用 UserCoordinator 后，state 获得 5 个字段：

| 字段 | 含义 | 约束 |
|------|------|------|
| `chat_message` | 给用户看的自然语言回复 | **始终非空**，即使 IS_EXECUTE=true |
| `matched_sop_id` | 匹配到的 SOP ID | 空字符串 或 在 `sops.csv` 白名单中 |
| `current_action` | 当前要执行的具体行动 | 渐进式确认中逐步填充 |
| `long_term_intent` | 用户的长期意图目标 | 仅 IS_EXECUTE=true 时有效 |
| `is_execute` | 执行闸门 | `"true"` 或 `"false"`（字符串，非布尔） |

### Thinker 阶段：意图分类

Thinker 接收 4 个信息源：`USER_MESSAGE`（用户输入）、`CURRENT_DIALOGUE`（当前对话上下文）、`CONVERSATION_HISTORY`（跨周期对话摘要）、`EXECUTION_HISTORY`（跨周期执行摘要），以及 `SOP_LIBRARY`（由 `build_sop_library_index()` 从 `sops.csv` 构造的精简索引文本，格式为 `SOP_ID | Objective | Description`，不包含完整 Plan_Steps）。

Thinker 基于这个轻量表示做语义匹配——匹配到的 SOP_ID 在后续加载阶段才会验证完整 Plan_Steps。Thinker 按系统 Prompt 引导的推理步骤工作：分析用户意图 → 浏览 SOP_LIBRARY → 匹配或判断需求 → 决定确认阶段 → 推导五字段值。

### Formatter + Validator 阶段

Formatter 从推理链提取五字段输出。`validator/UserCoordinatorValidator.py` 的 `_parse_fields()` 按行首标签（`CHAT_MESSAGE:`、`SOP_ID:`、`CURRENT_ACTION:`、`LONG_TERM_INTENT:`、`IS_EXECUTE:`）逐一匹配提取字段值。

Validator 的核心规则是**IS_EXECUTE 作为总闸**，分两个模式：

**IS_EXECUTE = "false"**（渐进确认模式）：
- `CHAT_MESSAGE` 必须非空
- `LONG_TERM_INTENT` 必须为 `NONE`
- `SOP_ID` 和 `CURRENT_ACTION` 可以为 NONE（当前阶段尚未确定）
- 若 `SOP_ID` 为 NONE，`CURRENT_ACTION` 也必须为 NONE

**IS_EXECUTE = "true"**（执行就绪模式）：
- 所有四个字段都必须非空非 NONE
- `SOP_ID` 必须在 `valid_sop_ids` 白名单中存在
- `LONG_TERM_INTENT` 必须有效

### 字段截断机制

`_parse_fields()` 有一个关键的防护设计：每个字段的值被截断到下一个字段标签出现的位置，防止多行值溢出跨字段边界。具体做法是按字段定义的固定顺序（CHAT_MESSAGE → SOP_ID → CURRENT_ACTION → LONG_TERM_INTENT → IS_EXECUTE），对每个字段值检查是否包含了后续字段的标签文本，若包含则从该标签位置截断。例如，若 `CHAT_MESSAGE` 输出的文本中意外包含了 "SOP_ID: xxx" 字样，截断机制确保它不会污染 `sop_id` 字段。

### IS_EXECUTE 闸门：代码硬开关

Agent 的执行权不在 LLM 手里，而在 `main.py` 中：当 `state.get("is_execute") == "true"` 时，展示完整摘要给用户，然后通过 `input()` 等待用户输入 `y`（确认执行）或 `n`（重新描述）或补充信息。`is_execute` 字段被存为字符串（`"true"` / `"false"`）而非 Python 布尔值——字符串比对 `== "true"` 是一个简单、可审计、不会被 LLM 幻觉绕过的硬开关。

### 渐进式确认三阶段

三级确认不是在一个 UserCoordinator 调用内完成的，而是**跨越多轮 REPL 循环**：

1. **Stage 1（SOP 匹配）**：UserCoordinator 分析用户意图，推荐匹配的 SOP → 输出 `IS_EXECUTE=false, SOP_ID=xxx` → 用户确认"是这个吗？"
2. **Stage 2（行动细化）**：UserCoordinator 识别缺失的具体信息（时间范围、目标目录等）→ 输出 `IS_EXECUTE=false, SOP_ID=xxx, CURRENT_ACTION=xxx` → 提供合理默认值
3. **Stage 3（最终确认）**：所有信息完备 → 输出 `IS_EXECUTE=true`，五字段全部填充 → `LONG_TERM_INTENT` 包含完整目标摘要 → 等待用户 `y/n`

`CURRENT_DIALOGUE` 字段追踪跨轮次的确认进度。每轮 `User`/`Agent` 消息追加到此字段，UserCoordinator 在 Thinker 阶段读取它来判断当前处于哪个确认阶段。

---

## 为什么这么做

### 4B 模型可能产生幻觉 —— 白名单校验兜底

qwen3:4b 可能在 SOP 匹配时编造不存在但"看起来合理"的 SOP_ID（如 `SYSTEM_CHECK` 而非已注册的 `FULL_SYSTEM_HEALTH_CHECK`）。如果直接信任 LLM 输出的 SOP_ID 去加载文件，会因文件不存在而崩溃。

在工厂创建时，从 `sops_df["SOP_ID"]` 构建有效 SOP ID 集合，传入 Validator 作为白名单。Validator 将 LLM 输出的 SOP_ID 与白名单比对——不在白名单中的 SOP_ID 被拒绝，触发 Formatter 重试。

### LLM 只能"建议"，代码才"决定"

LLM 的输出是概率采样，同一输入在不同时间可能产生不同输出。如果把执行权交给 LLM（例如 LLM 直接在输出中说"开始执行"），那么 Agent 可能在用户未确认时自行启动——对于执行操作类任务后果严重。

`if state.get("is_execute") == "true":` 这行代码是一个确定性检查。LLM 输出的 `IS_EXECUTE: true` 只意味着"我认为可以执行了"——代码用 `input()` 向用户做最后确认，用户输入 `y` 才真正进入执行图。

### 三级渐进确认降低用户一次性决策负担

如果要求用户一次性描述所有细节（"我要做什么、用哪个工具、参数是什么、目标范围"），大多数用户做不到。三步确认相当于结构化访谈——第一步搞清楚"是什么任务"，第二步搞清楚"具体怎么做"，第三步"确认执行"。每步都是一个简单问题。

用户在任何一步都可以打断：想修正就输入 `n` 重新进入 UserCoordinator；想补充就输入额外信息，被追加到 CURRENT_DIALOGUE，UserCoordinator 在下一轮处理。

### 字段截断防止输出污染

4B 模型可能在 `CHAT_MESSAGE`（自由文本）中意外输出类似标签的文本（例如在解释时写出 "我会设置 IS_EXECUTE: true"）。如果不截断，下游解析可能错误提取这些内嵌文本作为字段值。截断机制确保只有实际的结构化标签才被提取——这是一种防御性解析策略。

### 存疑时优先安全（归为 CHAT 或 UNCERTAIN）

Thinker 引导模型"如果不确定是否为可执行任务，优先归为 CHAT 或 UNCERTAIN"。代价是多问一轮；收益是避免错误执行。"宁可多问一句"的设计原则贯穿整个 UserCoordinator。

---

## 不这么做会怎样

### AutoGPT 式自主执行

传统的 AutoGPT / LangChain Agent 模式中，LLM 从用户意图直接推导出行动并执行，中间没有确认环节。LLM 说"我觉得你想清理磁盘"然后直接执行——没有机会让用户说"等等，不是这个目录"。对消费级 GPU 上的 4B 模型来说这尤其危险，因为幻觉概率远高于大模型。

### 不用白名单校验 SOP_ID

LLM 输出一个不存在的 SOP_ID，`sop_loader.load_sop_markdown()` 找不到文件 → 抛出异常或返回空数据 → 执行引擎启动时缺少 Plan_Steps → 崩溃。一个 LLM 幻觉导致整个流程中断。白名单将这种故障模式从"运行时崩溃"提前到"Validator 校验失败 → Formatter 重试"。

### 执行权交给 LLM

假设 IS_EXECUTE 不由代码闸门控制，而是 LLM 直接触发执行。那么 LLM 某次随机输出带 `IS_EXECUTE: true` 时，系统会绕过用户确认直接启动。这在 LLM 误判用户意图、上下文截断后配错 SOP_ID、高温输出随机波动等场景中很危险。代码闸门将 LLM 的随机性隔离在执行边界之前。

### 只做一次确认而非三级

如果只做一次确认——"我要做 X，对吗？[y/n]"——用户只能回答是或否。但如果用户想纠正的不是任务本身，而是一个参数呢？"不是检查根目录，是检查 /var/log"。三级确认让用户有机会在 Stage 2 中细化参数，而不是在 Stage 1 就否决整个匹配。
