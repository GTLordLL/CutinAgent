# SOP 编写规范

SOP 即代码。Plan_Steps 使用自然语言表达任务逻辑，同时受严格 DSL 格式校验。
每个规则与 `SopSpecChecker.py` 的校验逻辑一一对应——**不合规的 SOP 加载时直接拒绝**。

---

## 一、Section 清单（7 项）

| # | Section | 必填 | 说明 |
|---|---------|------|------|
| 1 | `## Objective` | 是 | 一句话任务目标 |
| 2 | `## Description` | 是 | 任务详细描述 |
| 3 | `## Keywords` | 否 | 关键词，逗号分隔 |
| 4 | `## Tools_Required` | 是 | 依赖的 Tool_ID，逗号分隔。所有 ID 必须存在于 `tools/tools.csv` |
| 5 | `## Retry_Limit` | 是 | 正整数（≥1）。全局重试硬上限 |
| 6 | `## Plan_Steps` | 是 | 步骤序列，每行 `N. 内容`。不能为空 |
| 7 | `## Global_Exception_Handling` | 是 | 异常条件 → 处理策略，每条规则一行 |

---

## 二、Plan_Steps 格式规则

### 2.1 行格式
每行必须以 `序号. ` 开头（数字 + 句点 + 至少一个空格）。示例：
```
1. 调用 locate_large_files(path=/var/log, limit=5)
2. FINISH。
```

### 2.2 序号约束
- **唯一**：同一步骤序号不能重复
- **连续**：从 1 到最大序号，不允许跳空。`1, 2, 4` 不合法，`1, 2, 3` 合法

### 2.3 内容约束
- **Plan_Steps 不能为空**
- 每步必须能被归类为以下 5 种类型之一（见第三节）

---

## 三、控制流（2 种）+ 终端标记（3 种）

SopSpecChecker 按优先级从高到低分类每个步骤：

### 3.1 终端标记

| 标记 | 语法 | 约束 |
|------|------|------|
| **FINISH** | `FINISH` 或 `FINISH。` | 最后一步必须是 FINISH。允许多个 FINISH（条件分支可提前终止）。至少有一个 |
| **INTERRUPT** | `INTERRUPT` 开头 | 仅允许作为独立终止步骤，或出现在条件分支内（`如果...就 INTERRUPT`） |
| **ERROR** | `ERROR` 或 `ERROR。` | 同上，仅允许作为独立步骤或条件分支内 |

### 3.2 并行执行（PARALLEL）

**优先级高于顺序/条件**——只要检测到并行句式，就归类为 PARALLEL。

| 子类型 | 句式 | 示例 |
|--------|------|------|
| 静态并行 | `同时调用 A(...) 和 B(...)` | `1. 同时调用 get_system_health(target='all') 和 check_system_sync()` |
| 动态集合并行 | `基于步骤X的{集合}，同时为其中每一个调用 tool(...)` | `2. 基于步骤1的大文件列表，同时为其中每一个大文件调用 check_file_access(path=该文件的完整路径)` |

约束：
- 最多同时调用 **3 个**工具
- 每步至少 1 个工具

### 3.3 条件选择（CONDITIONAL）

**句式**：`如果{条件}，就调用 tool_id(...)。`

约束：
- 必须包含 `如果...就` 模式
- INTERRUPT / ERROR 可出现在条件分支内

### 3.4 顺序执行（SEQUENTIAL）

**句式**：`调用 tool_id(param='value')`

约束：
- 必须包含至少一个 `tool_id(...)` 格式的工具调用
- tool_id 必须在 `tools/tools.csv` 中存在

---

## 四、Global_Exception_Handling 写法

每条规则格式：`序号. 如果{条件}，{处理动作}。`

处理动作包括：
- 调整参数重试（不超 Retry_Limit）
- 跳过步骤
- 标记 ERROR 并终止
- 输出已采集数据作为替代

原则：**重试由 SOP Execution Scheduler (LLM) 决策、ProgressUpdater (纯代码) 跟踪。SOP 只需设定 Retry_Limit 并在异常处理中描述最坏情况。**

---

## 五、校验规则速查表

| # | SopSpecChecker 检查项 | 本规范对应章节 |
|---|----------------------|--------------|
| 1 | 每行 `N. ` 开头 | 2.1 行格式 |
| 2 | 序号唯一 | 2.2 序号约束 |
| 3 | 序号连续 | 2.2 序号约束 |
| 4 | Plan_Steps 非空 | 2.3 内容约束 |
| 5 | 步骤类型可识别 | 三、控制流 |
| 6 | 最后一步 FINISH | 3.1 终端标记 |
| 7 | 至少 1 个 FINISH | 3.1 终端标记 |
| 8 | SEQUENTIAL 含 `tool_id(...)` | 3.4 顺序执行 |
| 9 | PARALLEL ≤3 工具 | 3.2 并行执行 |
| 10 | CONDITIONAL 含 `如果...就` | 3.3 条件选择 |
| 11 | INTERRUPT/ERROR 放置合法 | 3.1 终端标记 |
| 12 | tool_id 在 tools.csv 中 | 一、Section 清单 |
| 13 | Retry_Limit 正整数 | 一、Section 清单 |
