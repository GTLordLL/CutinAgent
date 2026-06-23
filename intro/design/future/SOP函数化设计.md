# SOP 函数化 — 统一工具与 SOP 的调用方式

> **状态：设计提案 (RFC)** — 尚未实现。v0.3 计划引入。
>
> **关联设计**：[[SOP体系设计]](../essentials/SOP体系设计.md) · [[工具合约设计]](../essentials/工具合约设计.md) · [[图结构与路由设计]](../essentials/图结构与路由设计.md) · [[Compactor设计]](../essentials/Compactor设计.md) · [[子SOP嵌套设计](子SOP嵌套设计.md) · [[ThinkerFormatter设计]](../essentials/ThinkerFormatter设计.md)

---

## 核心思路

将 SOP 从"外部流程"提升为**一等公民**：SOP 与工具使用完全相同的注册、调用和返回机制。LLM 看到的不再是"工具列表 + SOP 库"两套体系，而是一个统一的可用调用列表。

SOP 成为 `Tool_Type: composite`——一种内部驱动多轮 LLM 循环的复合工具。同时弃用 TaskCompactor（保留文件不删除），新增单阶段 `SopSummarizer` 负责执行总结。

### 当前痛点

```
用户输入 → ProblemAnalyzer → UserCoordinator
                                   │
                    ┌──────────────┼──────────────┐
                    ▼              ▼              ▼
              匹配 SOP_ID    调用 gather 工具    回复对话
                    │
                    ▼
              execute_sop_flow (确认→加载→图循环→Compactor→满意度)
```

1. **两套调用体系**：工具走 `ToolDispatcher.dispatch(tool_id, args)`，SOP 走 `execute_sop_flow` → LangGraph 循环。UserCoordinator 需同时输出 `matched_sop_id` 和 `tool_call`。
2. **SOP 不可被工具层调用**：ProblemAnalyzer 只能调 `gather` 工具，不能触发诊断类 SOP。
3. **SOP 不可嵌套**：Plan_Steps 无法调用另一个 SOP。
4. **TaskCompactor 过度设计**：Compactor 输出 3 字段（evaluation / conversation_summary / execution_summary），其中满意度判断（evaluation）和双份总结可简化为单角色单字段。
5. **概念负担**：`Tool_Type` 只有 `action` 和 `gather`，无法表达复合操作。

### 新架构

```
用户输入 → ProblemAnalyzer → UserCoordinator
                                   │
                                   ▼
                          返回 TOOL_CALL: GIT_SMART_COMMIT(files='.')
                                   │
                                   ▼
                          ToolDispatcher.dispatch("GIT_SMART_COMMIT", {files: '.'})
                                   │
                                   ▼
                          SOP 执行循环 (确认→图循环→SopSummarizer)
                                   │
                                   ▼
                          返回 {status, summary, detail}
```

核心变更：
- SOP 注册到 `tools/tools.csv`（`Tool_Type: composite`）
- SOP 注册到 `ToolDispatcher.toolbox`（闭包函数，签名 `(**kwargs) -> dict`）
- `ToolDispatcher.dispatch` 识别 `composite` → 触发 SOP 执行循环
- TaskCompactor **弃用但不删除**（文件保留），新增 `SopSummarizer`（单阶段，仅输出 SUMMARY）
- 满意度判断**删除**（Scheduler TASK_STATUS 替代，重试由 Scheduler 内部处理）
- 调用方无需区分工具和 SOP

---

## 具体变更

### 1. 注册层：tools.csv + ToolDispatcher

**tools.csv 新增**：
```csv
Tool_ID,Keywords,Tool_Type,Func_Desc,Args_Schema,param_desc
GIT_SMART_COMMIT,"GIT, commit, conventional-commits",composite,"扫描工作区变更，生成commit message并提交","{""files"": ""str (default .)""}",files: 要提交的文件范围
GIT_BRANCH_CLEANUP,"GIT, branch, cleanup, merged, delete",composite,"扫描本地分支，清理已合并的过期分支","{}",无需参数
GIT_PR_CREATE,"GIT, PR, pull-request, github",composite,"分析分支变更，生成PR描述，推送并创建PR","{""base"": ""str (default main)"", ""draft"": ""str (default false)""}",base: 目标分支
```

**ToolDispatcher 新增 composite 调度**：
```python
class ToolDispatcher:
    def __init__(self, resources, app_graph, ...):
        self.toolbox = {
            # ... 现有原子工具 ...
            "GIT_SMART_COMMIT": self._make_sop_handler("GIT_SMART_COMMIT"),
            "GIT_BRANCH_CLEANUP": self._make_sop_handler("GIT_BRANCH_CLEANUP"),
        }

    def _make_sop_handler(self, sop_id: str):
        """闭包工厂：让 SOP 看起来就是个 (**kwargs) -> dict 的函数"""
        def handler(**kwargs) -> dict:
            return self._execute_sop(sop_id, kwargs)
        return handler

    def _execute_sop(self, sop_id: str, params: dict) -> dict:
        sop_md = load_sop_markdown(sop_id, ...)
        sub_state = self._build_sub_state(sop_id, sop_md, params)
        state, _, final_status, _, _ = _iterate_graph_stream(
            self.app_graph, sub_state, node_callback=None
        )
        # 调用 SopSummarizer
        summary = self._run_sop_summarizer(state)
        # 追加到 execution_history
        state["execution_history"] = (
            state.get("execution_history", "") + f"\n[SOP:{sop_id}] {summary}"
        )
        return self._extract_sop_result(state, final_status, summary)

    def dispatch(self, tool_id: str, args: dict):
        func = self.toolbox[tool_id]
        resolved = self._resolve_vars(args)
        return func(**resolved)
```

关键点：从 `dispatch` 看来，SOP 就是一个签名为 `(**kwargs) -> dict` 的普通函数。多轮 LLM 循环被封装在 `_execute_sop` 内部。

### 2. SopSummarizer 新角色（替代 TaskCompactor）

**TaskCompactor**：弃用但不删除。`llm_nodes/TaskCompactorNode.py`、`validator/CompactorValidator.py`、`prompts/compactor/` 保留不动（不再被调用）。

**SopSummarizer**：全新单阶段角色。不需要 Thinker + Formatter 双阶段——"读执行记录，写 3 句总结"没有格式歧义，不需要多路径分支。

| 维度 | TaskCompactor（旧，弃用） | SopSummarizer（新） |
|------|--------------------------|---------------------|
| 阶段 | Thinker + Formatter 双阶段 | 单阶段 |
| 输出 | EVALUATION + CONVERSATION_SUMMARY + EXECUTION_SUMMARY | SUMMARY（1-3 句中文） |
| 调用时机 | SOP 图循环结束后 | 每个 SOP 图循环结束后（主 SOP + 子 SOP） |
| 满意度判断 | 输出 EVALUATION: 满意/不满意 | **不判断**，满意度逻辑删除 |
| 文件 | 3 个文件（弃用保留） | 3 个新文件 |

**SopSummarizer 输入/输出**：
```
输入:
  - USER_INSTRUCTION: 用户原始请求
  - EXECUTION_HISTORY: 所有工具调用的时序日志（截断到 4000 字符，取最近步骤优先）

输出:
  SUMMARY: 1-3 句中文，涵盖：做了什么、关键结果、最终状态
```

**数据流**：
```
SOP 图循环结束
  ↓
SopSummarizer → SUMMARY: "已提交 3 个文件，commit: feat(api): add auth。工作区干净。"
  ↓
追加到 execution_history: "[SOP:GIT_SMART_COMMIT] 已提交 3 个文件..."
追加到 conversation_history: "[SOP:GIT_SMART_COMMIT] 已提交 3 个文件..."
  ↓
SOP 返回值:
  status:  "完成" | "失败"（从 Scheduler TASK_STATUS 判断）
  summary: SUMMARY
  detail:  execution_history 原始内容[:2000]
```

**新增文件**：
```
prompts/execution_summarizer.md          ← 单 prompt，输出 SUMMARY
llm_nodes/SopSummarizerNode.py           ← 单阶段 LLM 调用工厂
validator/SopSummarizerValidator.py      ← 校验：非空 + ≤500 字符
```

**修改文件**：
```
utils/LLMResources.py     ← 加载 prompt + 创建 sop_summarizer_fn
main.py                   ← 实例化 sop_summarizer_fn
execution_controller.py   ← 图循环后调用 Summarizer，summary 追加到 execution_history
```

### 3. 调用链路简化

**变更前**：
```
input_handler._run_coordinator_and_execute
  → UserCoordinator LLM → matched_sop_id / tool_call
  → execute_sop_flow
    → 确认 → 加载 → 图循环 → TaskCompactor → 满意度 → RUN_SUMMARY
```

**变更后**：
```
input_handler._run_coordinator_and_execute
  → UserCoordinator LLM → TOOL_CALL: GIT_SMART_COMMIT(files='.')
  → ToolDispatcher.dispatch("GIT_SMART_COMMIT", {files: '.'})
    → _execute_sop
      → 确认 → 加载 → 图循环 → SopSummarizer
      → 返回 {status, summary, detail}
  → write_sop_run_summary
```

UserCoordinator 不再输出 `matched_sop_id` / `is_execute`。它只需要输出 `TOOL_CALL`——和 ProblemAnalyzer 完全相同的输出格式。SOP 还是工具，由 ToolDispatcher 根据 `Tool_Type` 自动路由。

**满意度删除**：原 Compactor 的 `EVALUATION` 字段删除。SOP 执行失败时由 Scheduler 内部 retry 处理（与原子工具一致），外部不再包满意度重试循环。`TASK_STATUS=FINISH` → 成功，`TASK_STATUS=ERROR` → 失败。

### 4. State 字段清理

| 操作 | 字段 | 原因 |
|------|------|------|
| 弃用（不消费） | `compactor_evaluation` | 满意度删除 |
| 弃用（不消费） | `compactor_conversation_summary` | 改为 Summarizer 写入 |
| 弃用（不消费） | `compactor_execution_summary` | 改为 Summarizer 写入 |
| 删除 | `matched_sop_id` | UserCoordinator 统一为 `TOOL_CALL` |
| 删除 | `is_execute` | 不再需要区分"执行 SOP"和"回复对话" |
| 保留 | `conversation_history` | ChatCompactor 仍写入，SopSummarizer 追加 |
| 保留 | `execution_history` | SopSummarizer SUMMARY 追加（不覆盖） |

### 5. 并行约束

LLM 节点不可能并行，只有工具-工具或工具-LLM 可并行。并行仅发生在 `ToolExecutor` 层面——当 Scheduler 输出多个 `|` 分隔的原子工具调用时。SOP（composite）内部有 LLM 循环，不与原子工具混合并行。

### 6. 参数化入口

SOP 参数通过 `Args_Schema` 声明，值从 `TOOL_CALL` 传入，通过 `VAR_` 在 Plan_Steps 中引用：

```
Plan_Steps:
1. 调用 get_git_status()
2. 调用 get_git_diff(staged=False, files=VAR_files)    ← 来自调用参数
3. 调用 generate_commit_message(data=VAR_get_git_diff)
4. FINISH。
```

调用 `GIT_SMART_COMMIT(files='src/auth.py')` → `VAR_files` 在执行前注入 VariableStore。

---

## 为什么这么做

1. **统一调用面降低 LLM 决策负担**：UserCoordinator 从三条输出路径（SOP_ID / tool_call / chat_message）简化为两条（TOOL_CALL / chat_message）。LLM 只需决定"调用哪个函数"。

2. **SOP 可组合，嵌套自然成立**：SOP 注册到 toolbox 后，Plan_Steps 中调用另一个 SOP 和调用原子工具无区别——都是 `ToolDispatcher.dispatch`，都返回 `{status, summary, detail}`。[[子SOP嵌套设计]](子SOP嵌套设计.md) 中复杂的 `CALL_SOP` 步骤类型退化为普通 SEQUENTIAL 步骤。

3. **消除冗余 LLM 调用 + 简化设计**：TaskCompactor 的 Thinker+Formatter 双阶段替换为 SopSummarizer 单阶段，每次 SOP 执行省去 1 次 Thinker 调用。满意度判断删除——Scheduler 的 TASK_STATUS 足以区分成功/失败，重试由 Scheduler 内部统一处理。

4. **最小侵入**：SopSummarizer 是纯增量角色，不影响 Scheduler、Compactor、UserCoordinator 的现有提示词。Compactor 文件保留不动，回滚零成本。

5. **参数化让 SOP 从硬编码变为可配置函数**：参数通过 `Args_Schema` 声明式定义，类型明确、默认值明确、可被 Formatter 校验。不再靠 LLM 在 Plan_Steps 文本中做脆弱的查找替换。

6. **保留 Markdown + LLM 循环的灵活性**（方案 A vs 方案 B）：不采用硬编码 Python 函数的方案 B，因为那会失去异常处理的自适应调整、条件分支的语义理解、参数的自适应能力。SOP markdown 仍是"源码"——人类可读、人类可写、LLM 可推理。

---

## 不变的部分

- 图结构（`graph/Builder.py`）：3 节点循环 `Scheduler → ToolExecutor → ProgressUpdater → Scheduler`
- SOP markdown 7 section 结构
- `sop/sops.csv` 索引格式
- SopSpecChecker 13 项校验
- 现有 SOP 的 Plan_Steps 无需修改
- 用户交互（确认）保留，移至 ToolDispatcher 内部
- ChatCompactor 保留不动
- `conversation_history` 字段保留（ChatCompactor + SopSummarizer 双写入源）
- `execution_history` 追加模式不变

---

## 迁移计划

原则：**提示词先行，代码后行**。LLM 行为变更是最大风险点，优先修改并验证，再跟进代码适配。SopSummarizer 作为纯增量角色，不影响任何现有节点。

### Phase 1：SopSummarizer 新角色

**目标**：新增单阶段总结角色，SOP 图循环结束后输出 SUMMARY，追加到 execution_history 和 conversation_history。

| 文件 | 操作 | 改动 |
|------|------|------|
| `prompts/execution_summarizer.md` | **新增** | 单 prompt，输入 USER_INSTRUCTION + EXECUTION_HISTORY（截断 4000 字符），输出 SUMMARY（1-3 句中文） |
| `llm_nodes/SopSummarizerNode.py` | **新增** | 单阶段 LLM 调用工厂 `build_sop_summarizer_fn()`，不走 Thinker+Formatter |
| `validator/SopSummarizerValidator.py` | **新增** | 极简校验：SUMMARY 非空 + ≤500 字符 |
| `utils/LLMResources.py` | 修改 | 加载 `execution_summarizer.md` + 创建 `sop_summarizer_fn` |
| `main.py` | 修改 | 实例化 `sop_summarizer_fn` |
| `execution_controller.py` | 修改 | 图循环后调用 Summarizer，summary 追加到 execution_history，组装 `{status, summary, detail}` 返回值 |

**风险**：低。纯增量角色，不影响任何现有节点。Summarizer 不参与执行控制流（不像 Compactor 输出 EVALUATION 影响满意度循环），输出仅用于展示和历史记录。

**验证标准**：在 3 个现有 SOP 上各跑 3-5 轮，SUMMARY 质量不低于当前 Compactor 的 `execution_summary`（不需要更优，但不能明显退步）。

**向后兼容**：此阶段 Compactor 仍被调用。Summarizer 和 Compactor 并存，Summarizer 输出暂时仅用于日志。

---

### Phase 2：UserCoordinator 提示词 — SOP 调用格式变更

**目标**：UC 输出从 `SOP_ID`（裸 ID）变为 `TOOL_CALL`（函数调用语法），统一工具和 SOP 的调用面。删除内部多步确认机制（外部 `_confirm_execution()` 已有确认面板），删除 CURRENT_ACTION / LONG_TERM_INTENT / IS_EXECUTE。

#### 2.1 提示词变更

**`thinker.md`**：

| 位置 | 旧 | 新 |
|------|----|----|
| `SOP_LIBRARY` 格式 | `SOP_ID \| Objective \| Description` | `SOP_ID(param: type = default): """description"""`（Python 函数签名，与 ProblemAnalyzer 的 `GATHERED_TOOLS`、Scheduler 的 `AVAILABLE_TOOLS` 统一） |
| 确认流程 | 三阶段（Stage 1 匹配 → Stage 2 细化 → Stage 3 闸门） | **删除**：外部 `_confirm_execution()` 已有确认面板，UC 不再内部管理确认状态机 |
| 推理步骤 | 分类 → 三阶段确认 | **四步推理**：Intent Classification → SOP Matching → Parameter Filling → Output（对标 ProblemAnalyzer 的 "Select Tools → Derive Parameters" 和 Scheduler 的 "Locate Next → Derive Parameters"） |
| CURRENT_ACTION 字段 | 输出 | **删除**（TOOL_CALL 的函数调用语法已自解释） |
| LONG_TERM_INTENT 字段 | 输出 | **删除**（Compactor 弃用后无消费者） |
| IS_EXECUTE 字段 | 输出，控制内部闸门 | **删除**（外部确认面板替代；TOOL_CALL 非 NONE 即表示"已匹配 SOP 并填好参数，可进入确认"） |

推理流程：

```
1. Classify User Intent  → CHAT / UNCERTAIN / EXECUTE
2. Handle by Category    → CHAT/UNCERTAIN: TOOL_CALL=NONE
                         → EXECUTE: proceed to step 3
3. SOP Matching          → 扫描 SOP_LIBRARY 函数签名，匹配最佳 SOP
                         → 无匹配: TOOL_CALL=NONE，建议可处理的范围
4. Parameter Filling     → 从 USER_MESSAGE / Analyzer 发现 / EXECUTION_HISTORY / 默认值 推导参数
                         → 构建 TOOL_CALL: SOP_ID(param='value', ...)
                         → CHAT_MESSAGE 解释选择和参数，请用户确认
```

边界情况：
- **无参 SOP**（`SYSTEM_DIAGNOSTIC()`）：输出空括号 `SOP_ID()`
- **无匹配 SOP**：CHAT_MESSAGE 诚实说明，建议可处理的范围，TOOL_CALL = NONE
- **参数缺失**：有默认值用默认值，无默认值在 CHAT_MESSAGE 中询问

TOOL_CALL 格式与 ProblemAnalyzer / Scheduler 完全一致：`Tool_ID(param='value', ...)`，无调用时写 `NONE`。不写 `|` 并行语法（SOP 是复合工具，内部有 LLM 循环，不同 SOP 不可并行）。

**`formatter.md`**：

输出字段从 5 个精简为 2 个：

```
旧格式:                              新格式:
CHAT_MESSAGE                         CHAT_MESSAGE
SOP_ID                 ──→           TOOL_CALL
CURRENT_ACTION         ──→ 删除
LONG_TERM_INTENT       ──→ 删除
IS_EXECUTE              ──→ 删除
```

```
CHAT_MESSAGE: <natural language response>
TOOL_CALL: <SOP_ID(param='value', ...)> or NONE
```

#### 2.2 代码适配

| 文件 | 改动 |
|------|------|
| `validator/UserCoordinatorValidator.py` | `SOP_ID` 集合成员检查 → `TOOL_CALL` 函数调用语法校验（复用 `parsers/tool_call.py` 的 `parse_single_call`）；`valid_sop_ids` 仍为 SOP 集合（UC 只调 SOP，不调原子工具）；删除 CURRENT_ACTION / LONG_TERM_INTENT / IS_EXECUTE 校验逻辑 |
| `llm_nodes/UserCoordinatorNode.py` | `map_result()` 从 TOOL_CALL 字符串提取 SOP_ID 部分（`tool_call.split('(')[0]`）写入 `matched_sop_id`；同时写入 `tool_call` 字段；不再写入 `current_action` / `long_term_intent` / `is_execute` |
| `repl/execution/execution_controller.py` | 确认面板从展示「SOP + 行动 + 长期计划」改为展示 `TOOL_CALL`（小改，约 3 行） |
| `cli/headless_runner.py` | `is_execute != "true"` 判断改为 `not tool_call or tool_call == "NONE"` |

**关键设计决策**：
- `IS_EXECUTE` 彻底删除：外部 `_confirm_execution()` 已有确认面板，无需 UC 内部再维护闸门状态
- TOOL_CALL 非 NONE 即表示"已匹配 SOP 并填好参数，可进入外部确认"
- `matched_sop_id` 仍写入 state（从 TOOL_CALL 提取），下游 `execute_sop_flow` 链路不变
- UC 的 TOOL_CALL 不写 `|` 并行语法——SOP 是复合工具，一次只执行一个
- `CURRENT_ACTION` / `LONG_TERM_INTENT` 彻底删除

**风险**：低。四步推理对标 ProblemAnalyzer / Scheduler 已验证的推理模式，LLM 无需管理内部确认状态机，token 消耗更少。

**验证标准**：在 3 个 SOP 上各跑 5 轮，SOP 匹配 + 参数推导准确率不低于当前三阶段模式。

---

### Phase 3：弃用 Compactor + 删除满意度

**目标**：用 SopSummarizer 替换 TaskCompactor，删除满意度判断循环，execution_controller 大幅瘦身。

| 文件 | 操作 |
|------|------|
| `execution_controller.py` | 移除 Compactor 调用；移除满意度 `while` 循环；改为调用 SopSummarizer；从 ~450 行瘦身到 ~50 行 |
| `execution_helpers.py` | `record_compactor_summaries` 改为从 SopSummarizer SUMMARY 读取并写入 |
| `llm_nodes/TaskCompactorNode.py` | **保留不动**（不再调用） |
| `validator/CompactorValidator.py` | **保留不动** |
| `prompts/compactor/thinker.md` | **保留不动** |
| `prompts/compactor/formatter.md` | **保留不动** |
| `main.py` | 不再创建 `task_compactor_fn` |
| `LLMResources.py` | 不再加载 compactor prompts |

**风险**：低（前提是 Phase 1 已验证 SopSummarizer 总结质量）。

**向后兼容**：Compactor 文件全保留，回滚只需恢复 `execution_controller.py` 中的 Compactor 调用。

---

### Phase 4：ToolDispatcher 注册层 + execution_controller 瘦身

**目标**：SOP 注册到 toolbox，`dispatch()` 统一路由工具和 SOP。

| 文件 | 改动 |
|------|------|
| `tools/tools.csv` | 新增 3 行 `composite` 类型 |
| `tools/ToolDispatcher.py` | 构造函数注入 `resources`/`app_graph`/`console`/`session_dir`/`headless`；新增 `_make_sop_handler` + `_execute_sop` + `_run_sop_summarizer` |
| `data_nodes/ToolExecutor.py` | ToolDispatcher 实例化方式改为接收注入实例 |
| `repl/execution/input_handler.py` | `is_execute="true"` → `ToolDispatcher.dispatch(tool_call)` |
| `graph/OverallState.py` | 删除 `matched_sop_id` / `is_execute` / `current_action` / `long_term_intent` |

**风险**：中。ToolDispatcher 构造函数签名变化影响 `main.py` 和 `ToolExecutor.py` 两处实例化。

---

### Phase 5：ToolExecutor 并行化（可选）

**目标**：多原子工具调用时走 ThreadPoolExecutor 并行执行。

**约束**：仅并行原子工具（非 composite）。LLM 节点不并行。SOP（composite）内部有 LLM 循环，不与原子工具混合并行。

| 文件 | 改动 |
|------|------|
| `data_nodes/ToolExecutor.py` | 新增 ThreadPoolExecutor 并行路径（仅原子工具）；单调用保持现有路径 |

**风险**：中。取消令牌线程安全、TUI 多面板渲染需适配。可独立于 Phase 1-4 实施。

---

## 依赖关系

```
Phase 1 (SopSummarizer) ──→ Phase 3 (弃用 Compactor) ──→ Phase 4 (ToolDispatcher)
Phase 2 (UC 提示词) ───────────────────────────────────→ Phase 4 (ToolDispatcher)
                                                                  Phase 5 (并行化，独立)
```

- Phase 1 和 Phase 2 **互相独立**，可并行实施
- Phase 3 依赖 Phase 1（需要 SopSummarizer 就位才能替换 Compactor）
- Phase 4 依赖 Phase 2（ToolDispatcher 接收 TOOL_CALL 格式）和 Phase 3（execution_controller 已瘦身）
- Phase 5 完全独立

---

## 与子 SOP 嵌套设计的关系

| 维度 | SOP 函数化 (本设计) | 子 SOP 嵌套 |
|------|-------------------|-----------|
| 核心变更 | SOP 注册为 toolbox 函数 | Plan_Steps 中 CALL_SOP |
| LLM 视角 | SOP = 工具，统一调用语法 | 父 SOP 显式引用子 SOP |
| 嵌套实现 | ToolDispatcher 递归调用 | 调用栈 Push/Pop |
| 依赖关系 | 不依赖子 SOP 嵌套 | 可从本设计受益 |

如果先实现本设计，子 SOP 嵌套的 `CALL_SOP` 可简化为普通工具调用——Scheduler 无需区分，ToolDispatcher 自动识别 `composite` 并递归执行。

最终形态：
```
ToolDispatcher.toolbox = {
    "get_git_status": <原子工具>,
    "GIT_SMART_COMMIT": <复合 SOP>,
    "GIT_PR_CREATE": <复合 SOP>,
    "SYSTEM_DIAGNOSTIC": <复合 SOP>,   # 可被 ProblemAnalyzer 调用
}

GIT_PR_CREATE(base='main')
  → _execute_sop → Scheduler 第1轮: get_git_status() | get_git_commits_ahead()
  → Scheduler 第3轮: GIT_BRANCH_CLEANUP()   ← SOP 嵌套调用另一个 SOP
    → ToolDispatcher.dispatch("GIT_BRANCH_CLEANUP", {})
      → _execute_sop → 图循环 → SopSummarizer → 返回 {status, summary, detail}
      → 父 SOP execution_history 追加: "[SOP:GIT_BRANCH_CLEANUP] 已删除 3 个过期分支..."
  → Scheduler 第5轮: FINISH
  → SopSummarizer → 返回 {status, summary, detail}
```

所有调用走同一个 `ToolDispatcher.dispatch` 入口，遵守同一个三字段契约。每个 SOP（父/子）结束后独立调用 SopSummarizer，summary 追加到 execution_history 形成完整追溯链。
