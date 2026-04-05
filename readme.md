暂时先全部使用qwen2.5-coder:7b，不用考虑模型选择，因为当前任务需要思维缜密和计划全面。
我在想，到底怎么才能让这个需求分析与计划设计，能够达到：
1.正确认识用户需求和评估需求复杂度；
2.拆分出子任务时，需要判断，这个子任务是否只需要调用一次工具或写不超过3000字符的代码，如果达不到这种复杂程度，那么就只需要大致拆分，只要保证整体思路不出错就行，任务是否复杂度状态机设置为“比较复杂”；如果判断满足，只需要调用一次工具或写不超过3000字符的代码，那么复杂度状态机设置为“不复杂，可以开始执行”。
3.将复杂度状态机中“比较复杂”的任务输入模型，分别重复1和2（递归）；
4.到最后所有子任务会被拆解成大模型最有把握做好的任务时，开始Formatter (Function Calling)

你现在的构思已经从单纯的“分流”进化到了 **递归任务拆解（Recursive Task Decomposition）**。这正是处理复杂工程问题的核心逻辑：**将一个无法直接执行的“大目标”，递归拆解为模型有 100% 把握执行的“原子操作”。**

在 **Ubuntu (RTX 3060)** 环境下，针对 `qwen2.5-coder:7b` 的特性，我们可以设计一套基于 **“执行阈值（Execution Threshold）”** 的递归架构。

---

### 1. 核心逻辑设计：基于阈值的递归

我们要引入一个关键的判断指标：**“可单步执行性 (Atomic Executability)”**。

* **原子任务定义**：只需调用 **1 次工具**（如 `execute_bash`）或编写 **< 3000 字符**代码即可完成的任务。
* **状态机切换**：
    * **COMPLEX (比较复杂)**：模型认为当前步骤仍需多步操作。操作：**递归进入下一层拆解**。
    * **READY (可以执行)**：模型确认该步骤为原子操作。操作：**停止拆解，送往 Formatter**。





ai生成自动化工作流的agent框架：
我将生成自动化工作流的过程，划分出了五个角色：
1.信息整合员：输入用户自然语言指令，系统环境配置信息和所有工具调用描述列表；输出可能要用到的所有工具编码和系统环境是否齐全；负责根据用户指令，从工具的描述和分类中，检索并推测出可能要用到的所有工具编码，并总结系统环境信息；
2.任务规划师：输入用户自然语言指令，工具编码和环境信息；输出任务计划书；负责大致规划任务，要求全面但不具体，保证大方向正确；
3.任务规划审计员：输入任务计划书；使用function calling的功能，输出判断计划是否全面字段；负责审核任务规划师输出的计划是否全面，不全面则给出理由并退回任务规划师重做；
4.原子任务审计员：输入任务计划书中的单项任务；使用function calling的功能，输出任务状态机COMPLEX (比较复杂)或 READY (可以执行) + 任务格式；负责判断原子任务和格式输出；
5.原子任务拆解员：输入标记为COMPLEX的任务，和他的父任务+兄弟任务（保证连贯性）；输出原子任务；负责将标记为COMPLEX的任务拆解成原子任务
最后全流程记录在文件中，得到一个任务树，树的叶子节点就是原子任务。
帮我写这五个角色的提示词


基于执行阈值（Execution Threshold）的递归架构。将一个无法直接执行的“大目标”，递归拆解为模型有 100% 把握执行的“原子操作。
我们要引入一个关键的判断指标：“可单步执行性 (Atomic Executability)”。
原子任务定义：只完成一个物理动作（如：写一个不超过50行的代码（约1500字符）、调一个 API、运行一个命令）。

状态机切换：
COMPLEX (比较复杂)：模型认为当前步骤仍需多步操作。操作：递归进入“原子任务拆解员”拆解；
READY (可以执行)：模型确认该步骤为原子操作。操作：封装任务格式：任务号+任务描述+工具编号。




### ## Reference Examples

#### **Example 1: [PASS] - Perfect Logical Alignment**
**input:**
**USER_INSTRUCTION:** "Check if the system temperature is over 75°C and log a warning if it is."
**SEMANTIC_CHAIN:** 1. Get current CPU temperature -> 2. Compare temperature against 75°C threshold -> 3. Save a warning message to the log file.
**WORKFLOW_DAG:**
1. [get_temp] -> dep: None | input: None | out: v1 # Get current CPU temperature
2. [try_check] -> dep: 1 | prompt: "Is {v1} greater than 75? Output 'OVERHEAT' or 'NORMAL'" | out: r1 # Compare temperature against 75°C threshold
3. [log_append] -> dep: 2 | input: r1 | out: s1 # Save a warning message to the log file

**output:**
`PASS | The SEMANTIC_CHAIN perfectly maps to the user's intent, and the WORKFLOW_DAG implementation correctly uses a dynamic node for the critical decision step.`

---

#### **Example 2: [FAIL] - The "Semantic Gap" Trap**
**input:**
**USER_INSTRUCTION:** "Analyze the network logs and email me the summary if there are any errors."
**SEMANTIC_CHAIN:** 1. Read the network log file -> 2. Send the raw log content via email.
**WORKFLOW_DAG:**
1. [cat] -> dep: None | input: "network.log" | out: v1 # Read the network log file
2. [send_mail] -> dep: 1 | input: v1 | out: s1 # Send the raw log content via email

**output:**
`FAIL | Semantic Gap: The SEMANTIC_CHAIN reveals a missing 'Analysis' step. The user requested a 'summary of errors', but the workflow is logically jumping from reading raw data to sending it without filtering or processing.`

---




### 1. 深度分析型（测试逻辑链条）
这个案例测试 `Architect` 是否懂得利用 `try_*` 节点进行数据二次加工，而不是直接把原始数据丢给用户。

* **USER_INSTRUCTION**: "帮我分析一下当前系统负载情况。如果负载过高，请列出磁盘占用最大的前 3 个文件夹。"
* **期望表现**:
    1.  **Selector**: 应该选出 `uptime` 和 `du`。
    2.  **Architect**: 
        * Step 1: `[uptime]` 获取负载。
        * Step 2: `[try_check_load]` 判断负载（决策节点）。
        * Step 3: `[du]` 获取文件夹大小。
        * Step 4: `[try_filter_top3]` 对 `du` 的结果进行排序和筛选。
* **审计要点**: `Auditor` 需要检查“判断负载”和“筛选前三”这两个逻辑动作是否有对应的节点。

---

### 2. 故障排查型（测试数据关联）
这个案例测试 `Architect` 能否根据模糊的目标，自动串联起“搜索 -> 读取 -> 分析”的链路。

* **USER_INSTRUCTION**: "在当前目录下找一下所有的 .log 文件，搜寻里面包含 'error' 的行，并告诉我这些错误大概是什么原因导致的。"
* **期望表现**:
    1.  **Selector**: 应该选出 `find` 和 `grep`（可能还有 `cat`）。
    2.  **Architect**: 
        * Step 1: `[find]` 定位所有 `.log`。
        * Step 2: `[grep]` 在这些文件中搜索 `'error'`。
        * Step 3: `[try_analyze_errors]` 核心步骤！将 `grep` 的输出作为输入，让子代理分析原因。
* **审计要点**: 如果 `Architect` 只是搜出了错误行而没有最后的 `try_analyze` 步骤，`Auditor` 应当判定为 `FAIL`（未完成“告诉我原因”的指令）。

---

### 3. 系统体检型（测试多工具协同）
这个案例测试系统处理复杂、多任务并行指令的能力。

* **USER_INSTRUCTION**: "做一次系统全面检查：看看内存够不够、磁盘空间还剩多少、以及网络接口状态是否正常。"
* **期望表现**:
    1.  **Selector**: `free`, `df`, `ip`。
    2.  **Architect**: 
        * 生成 3 条并行的静态工具调用。
        * 最后增加一个 `[try_summary]` 节点，将 `v1(mem)`, `v2(disk)`, `v3(net)` 全部作为输入，生成一份体检报告。
* **审计要点**: 检查 `try_summary` 是否同时依赖了前三个步骤。

---

### 4. 边界压力案例（故意“调戏” Agent）
这个案例专门用来测试你的 `should_design_workflow` 路由和 `Auditor` 的严谨性。

* **USER_INSTRUCTION**: "帮我写一段 Python 代码来实现斐波那契数列。"
* **预期行为**:
    1.  **Selector**: 应该发现工具表中没有任何工具能“写代码”，返回 `[]`。
    2.  **Route**: 触发 `should_design_workflow` 返回 `summarizer`。
    3.  **Summarizer**: 直接回复“抱歉，我目前的工具库仅支持 Linux 系统运维，无法为您编写代码”。

---

