# SOP 体系 — 自然语言即代码

## 做了什么

CutinAgent 的 SOP 不是 Python 代码，而是结构化 Markdown 文件。每个 SOP 包含 7 个标准 section：`Objective`、`Description`、`Keywords`、`Tools_Required`、`Retry_Limit`、`Plan_Steps`、`Global_Exception_Handling`。其中 Plan_Steps 是核心——用自然语言表达任务步骤，同时受严格的 DSL 格式约束。

**Plan_Steps 支持三种控制流**：
- **顺序**：`1. 调用 get_system_health(target='all')` —— 编号步骤逐行执行
- **条件**：`2. 如果 CPU 使用率超过 80%，就调用 list_top_processes(sort_by='cpu')。如果所有指标正常，则跳过本步骤。`
- **并行**：`1. 同时调用 get_system_health() 和 check_system_sync()`

从计算理论角度，顺序 + 条件 + 迭代构成了结构化程序定理的完备基础，足以表达任意任务逻辑。

**加载时校验**：`SopSpecChecker`（纯代码，不调 LLM）在 SOP 加载时执行 13 项规则校验——步骤编号必须连续、引用的工具 ID 必须存在于 `tools/tools.csv`、最后一步必须是 FINISH、INTERRUPT/ERROR 只能出现在条件分支内。校验失败直接抛出 `ValueError` 拒绝加载，不会进入运行时。

**CSV 索引**：`sops.csv` 维护所有 SOP 的 ID、Objective、Description、Keywords，由 `build_sop_library_index()` 构造为轻量文本供 UserCoordinator 做语义匹配。

## 为什么这么做

Markdown 是人类和 LLM 的共同语言。人写 SOP 就像写 TODO 清单——不需要学 DSL 语法，不需要在 GUI 画布上拖拽连线。与此同时，`SopSpecChecker` 的 13 项规则确保"看起来像自然语言"的步骤在结构上是严格合法的——工具存在、编号连续、终止条件明确。自然语言的灵活性 + 代码校验的确定性，两者兼得。

对比 Dify 式拖拽工作流：在画布上表达条件分支和迭代循环需要反复调整节点和连线，改一个步骤意味着重新布局整个图。而 Markdown 文件改一行文字就完成——"如果 CPU 超过 80% 就调用 list_top_processes"比画两个条件分支节点直观得多。

## 不这么做会怎样

如果 SOP 是纯 Python 代码——普通用户无法编写，LLM 也难以自动生成。如果 SOP 是纯自然语言（无校验）——步骤 3 引用了一个不存在的工具 ID，这个错误要到运行时 Scheduler 尝试调用时才暴露，浪费了前面两轮的 LLM 推理和工具执行。
