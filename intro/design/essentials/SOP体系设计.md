# SOP 体系 — Markdown 存储与加载时校验

## 做了什么

CutinAgent 的 SOP 以 Markdown 文件形式存储在 `sop/` 目录，通过 CSV 索引供 UserCoordinator 语义匹配，加载时经 SopSpecChecker 的 13 项 DSL 规则严格校验。

### 七 Section 标准结构

每个 SOP Markdown 文件包含 7 个标准 section（`## Section` 二级标题）：

| Section | 用途 | 运行时角色 |
|---------|------|-----------|
| `## Objective` | 一句话目标 | 可供 UserCoordinator Thinker 读取 |
| `## Description` | 场景描述 | 同上 |
| `## Keywords` | 逗号分隔的搜索关键词 | `sops.csv` 中也有关键词，Markdown 中的作为补充 |
| `## Tools_Required` | 逗号分隔的工具 ID 列表 | Scheduler 加载 SOP 时过滤可用工具集 |
| `## Retry_Limit` | 全局重试上限（正整数 >= 1） | ProgressUpdater 重试计数上限 |
| `## Plan_Steps` | 编号步骤列表（核心） | Scheduler 读取 + ProgressUpdater 追加进度 |
| `## Global_Exception_Handling` | 全局异常条件 | Scheduler Thinker 每轮扫描匹配 |

### Markdown 加载与 Section 提取

`utils/sop_loader.py` 的 `load_sop_markdown()` 按 `## Section` 正则逐一提取各 section 内容。正则使用 `(?=\n##\s|\Z)` 前瞻断言确保提取到下一个 section 标题或文件末尾停止，防止跨 section 串内容。返回的 dict 包含 `objective`、`description`、`plan_steps`、`tools_required`、`keywords`、`exception_handling`、`retry_limit`。

### CSV 索引与轻量匹配

`sop/sops.csv` 维护 SOP 索引（4 列：`SOP_ID`, `Objective`, `Description`, `Keywords`）。`utils/sop_loader.py` 的 `build_sop_library_index()` 将其转换为 `SOP_ID | Objective | Description` 格式的精简文本。这个精简文本被放入 `SOP_LIBRARY` 供 UserCoordinator Thinker 做语义匹配，不包含 Keywords（减少噪声）和 Plan_Steps 全文（减少 token 消耗）。

### SopSpecChecker：加载时 13 项校验

`validator/SopSpecChecker.py` 的 `check_sop_plan_steps()` 在 `load_sop_markdown()` 中被自动调用，校验失败直接 `raise ValueError` 拒绝加载。校验分两 Pass：

**Pass 1：逐行解析**（每行 `N. 步骤文本`）：

| # | 规则 | 违规行为 |
|---|------|---------|
| 1 | 每行必须以 `N. ` 开头 | 步骤缺少编号前缀 |
| 2 | 步骤序号不能重复 | 两个步骤都标为 `1.` |
| 3 | 步骤类型必须可识别 | 文本不含 `调用`/`如果...就`/`同时调用`/`FINISH` |
| 4 | INTERRUPT/ERROR 仅允许在条件分支内或作为终止步骤 | 顺序步骤正文中出现 INTERRUPT |
| 5 | 引用的工具 ID 必须在 `tools.csv` 中存在 | 工具名拼写错误 |
| 6 | SEQUENTIAL 步骤必须包含 `调用 tool_id(...)` | 顺序步骤只写了描述没写工具调用 |
| 7 | PARALLEL 步骤最多同时 3 个工具 | 同时调用 5 个工具 |
| 8 | CONDITIONAL 步骤必须包含 `如果...就` 句式 | 条件步骤只写了条件没写动作 |

**Pass 2：全局检查**：

| # | 规则 | 违规行为 |
|---|------|---------|
| 9 | Plan_Steps 不能为空 | 文件缺少 Plan_Steps section |
| 10 | 步骤序号必须连续（1..max_step 无跳空） | 步骤编号 1, 2, 4（缺 3） |
| 11 | 最后一步必须是 FINISH | 最后一步是 ERROR |
| 12 | 至少有一个 FINISH | 所有步骤都是 SEQUENTIAL |

**独立校验 13**：`check_retry_limit()` 单独校验 Retry_Limit 字段，必须是 >= 1 的正整数。非数字或 < 1 的值都会产生明确的错误信息。

### 步骤类型分类

`parsers/sop_plan.py` 的 `_classify_step()` 按优先级检测步骤类型。优先级从高到低：

```
FINISH > INTERRUPT > ERROR > PARALLEL > CONDITIONAL > SEQUENTIAL > UNKNOWN
```

- **FINISH**：以 `FINISH` 开头 —— 显式终止标记
- **INTERRUPT**：以 `INTERRUPT` 开头 —— 等待人工介入
- **ERROR**：以 `ERROR` 开头 —— 不可恢复的错误出口
- **PARALLEL**：包含 `同时调用` 或 `基于...同时为每一个` —— 并行执行
- **CONDITIONAL**：包含 `如果...就` —— 条件分支
- **SEQUENTIAL**：包含 `调用` —— 默认顺序执行

`_parse_steps()` 按 `N. ` 正则分割 Plan_Steps 文本为步骤列表，每个步骤包含 `number`、`header`、`sub_lines`。`_reconstruct_plan()` 将修改后的步骤列表重建为用于存储的完整文本——这是 ProgressUpdater 更新 SOP_PLAN 的基础。

### 校验时机

校验在 `load_sop_markdown()` 中立即执行，而非延迟到运行时。`valid_tool_ids` 是从 `tools.csv` 构建的工具 ID 白名单。校验失败时 error_msg 包含每个错误的行号、步骤编号、严重级别和人类可读信息。

### Tools_Required 过滤

Scheduler 加载 SOP 时检查 `Tools_Required` 字段。如果非空，将工具列表过滤为仅包含指定的工具 ID，缩小 LLM 在 Thinker 阶段的决策空间。过滤通过 pandas DataFrame 的 `isin()` 操作实现。

---

## 为什么这么做

### Markdown 是人机共同语言

人写 SOP 就像写 TODO 清单：编号步骤、条件判断、终止条件——直观易懂。LLM 能读取 Markdown 结构并理解 `## Section` + `N. 步骤` 格式。对比 Dify 式拖拽工作流：在画布上表达条件分支和迭代循环需要反复调整节点和连线，写 SOP Markdown 只需改文字。"如果 CPU 超过 80% 就调用 list_top_processes" 比画两个条件分支节点直观得多。

### 加载时校验 = 编译期错误

将 SOP 验证从运行时提前到加载时，是框架最关键的架构决策之一。类比编程语言：语法错误应在 IDE / lint 阶段发现，而非部署后在生产环境崩溃。

运行时校验的代价：步骤 3 引用了一个不存在的工具 ID → 要到该步骤被 Scheduler 调度时才发现 → 前两步的工具调用和 LLM 推理已经浪费了。加载时校验的代价：文件加载时多花约 10ms 执行 13 项检查 → 零运行时浪费。

校验失败抛出 `ValueError` 而非静默修正，因为格式错误的 SOP 不应被执行——修正权留给 SOP 作者。

### 校验器分层：Pass 1（行级）+ Pass 2（全局）

Pass 1 检查每行的独立属性（格式、类型、工具 ID），Pass 2 检查跨行的关系约束（连续性、终止条件）。两阶段分离让错误信息更精确——行 5 缺少工具调用 和 整个 Plan 缺少 FINISH 是不同层面的问题，分离后各自的诊断信息更具体。

### 步骤分类的优先级设计

`_classify_step()` 的优先级顺序不是任意的。FINISH/INTERRUPT/ERROR 必须在最前面——它们是终端步​骤类型，优先级最高，因为含有这些关键字的行即使也包含 `调用`（如 `FINISH 任务完成。调用 report_generator(...)` 生成摘要报告），也应被分类为 FINISH 而非 SEQUENTIAL——以确保最后一步被正确识别为终止步骤（Pass 2 校验要求最后一步是 FINISH）。PARALLEL 在 CONDITIONAL 之前，因为 `同时` 是一个更强的动作信号。

### 步骤编号连续性的强制约束

编号连续性（1, 2, 3...无跳空）提供了两个好处：可验证性（跳空意味着步骤被遗忘或错误复制，容易在加载时检测）和 ProgressUpdater 依赖（跳过间隙填充假设步骤按数字顺序排列，跳空会破坏这个逻辑）。

### Tools_Required 作为 Scheduler 的注意力限制

当 SOP 只需要 2 个工具时，给 Scheduler Thinker 展示 11 个工具签名会浪费上下文且增加误选风险。`Tools_Required` 过滤将 Scheduler 的决策空间从 N 个可能的工具调用缩小为 M 个——这对 4B 模型的可靠性有可测量的提升。

---

## 不这么做会怎样

### SOP 是纯 Python 代码

普通用户无法编写。LLM 难以自动生成（需要理解 Python 语法和框架 API）。维护成本高——加一个 SOP 需要写 Python 函数、注册路由、处理异常。而 Markdown SOP：新增一个 SOP 只需写一个 `.md` 文件 + 在 `sops.csv` 中加一行。

### 纯自然语言无校验

步骤 3 写 "调用 get_system_info(cpu=true)" —— 但 `get_system_info` 不存在，正确的工具 ID 是 `get_system_health`。没有 SopSpecChecker 的话，这个错误在 Scheduler 试图调用时才暴露。前两轮工具调用已经完成且无法回滚，第三轮的 LLM 推理也浪费了。用户看到的是"工具不存在"，而真正的浪费是不可见的。

### 运行时校验而非加载时

校验在 SOP 执行中（而非加载时）进行 → 发现错误时 SOP 已经部分执行 → 状态可能已被修改 → 要么强制终止（留下未完成的状态），要么尝试回滚（没有事务机制）。

### 无编号连续性要求

1. 收集系统数据 → 2. 分析数据 → 4. 生成报告。步骤 3 缺失但没有人注意到。Scheduler 执行 "步骤 4" 时可能缺少步骤 3 本应产生的 VAR_ 变量 → 运行时报错。连续性约束在加载时捕获这个问题。

### 无 Tools_Required 过滤

Scheduler 的 Thinker prompt 中包含全部 16 个工具的签名。对于一个只需要 `get_git_diff` 的 SOP，Scheduler 仍需要浏览 15 个不相关的工具签名。4B 模型的注意力分散 → 更可能选择错误的工具 → 增加了不必要的 Formatter 重试。
