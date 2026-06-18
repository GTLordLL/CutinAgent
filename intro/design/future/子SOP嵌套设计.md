# 子SOP嵌套 — 可组合的长任务支持

> **状态：设计提案 (RFC)** — 尚未实现。本文档描述 v0.3 计划引入的架构变更。
>
> **关联设计**：[[SOP体系设计]](../essentials/SOP体系设计.md) · [[图结构与路由设计]](../essentials/图结构与路由设计.md) · [[进度更新与重试设计]](../essentials/进度更新与重试设计.md) · [[问题分析员设计](问题分析员设计.md) · [[工具合约设计]](../essentials/工具合约设计.md)

---

## 做了什么

将单层 SOP 扩展为**可嵌套的多层 SOP 体系**，一个 SOP 的 Plan_Steps 中可以引用另一个 SOP 作为子步骤（类似函数调用）。子 SOP 拥有独立的执行上下文、独立的进度追踪、独立的变量作用域，执行完毕后将结果返回给父 SOP。

### 当前痛点：SOP 是平的，无法表达长任务

目前三个操作类 SOP（`GIT_SMART_COMMIT`、`GIT_BRANCH_CLEANUP`、`GIT_PR_CREATE`）各自独立，每个 SOP 的 Plan_Steps 是一组扁平的工具调用序列。这在简单场景下够用，但遇到以下需求就力不从心：

1. **组合任务**：用户说 "检查仓库健康状态，然后提交" → 这需要信息收集 + `GIT_SMART_COMMIT` 两个 SOP 的顺序组合。当前没有机制让一个 SOP 调用另一个 SOP，用户需要分两次交互完成。
2. **长任务链**：一个复杂的系统诊断可能包含 "收集系统指标 → 分析异常 → 如果异常则深度检查 → 生成修复建议 → 如果用户确认则执行修复"。每一步本身可能就是一个完整的 SOP。
3. **复用**：多个 SOP 共享同一个子流程（如 "收集 Git 状态" 这个子流程，在 `GIT_SMART_COMMIT` 和 `GIT_PR_CREATE` 中都需要），当前只能复制粘贴步骤文本。

子 SOP 嵌套本质上是用**函数调用的思想**组织 SOP：每个 SOP 是一个可独立执行、可被其他 SOP 调用的"函数"。

### 新语法：CALL_SOP 步骤类型

在 Plan_Steps 中新增第五种步骤类型 `CALL_SOP`（当前已有 SEQUENTIAL、CONDITIONAL、PARALLEL、FINISH）：

```
5. 调用 GIT_BRANCH_CLEANUP()
6. 如果分支清理成功，就调用 GIT_SMART_COMMIT(message=VAR_cleanup_result)
```

`CALL_SOP` 的解析优先级在 PARALLEL 之后、CONDITIONAL 之前（因为它可以出现在条件分支中）：

```
FINISH > INTERRUPT > ERROR > PARALLEL > CALL_SOP > CONDITIONAL > SEQUENTIAL
```

**语法格式**：
```
N. 调用 SOP_ID(arg1=value1, arg2=VAR_xxx)
N. 同时调用 SOP_A(...) | SOP_B(...)    # 并行调用两个子SOP
N. 如果条件，就调用 SOP_X(...)           # 条件子SOP调用
```

**参数传递**：子 SOP 接收命名参数。参数值可以是字面量（`"today"`）或 `VAR_` 引用（`VAR_get_git_diff`）。子 SOP 的 `user_instruction` 被自动设置为参数化后的任务描述。

### 调用栈式状态管理

当前 `task_status` 是平铺的字符串（`"ONGOING"` / `"FINISH"` / `"ERROR"` / `"INTERRUPT"`），适用于单层 SOP。引入子 SOP 后，需要**调用栈**来追踪嵌套层级。

#### State 新增字段

```python
# OverallState 新增字段
sop_call_stack: list[dict]   # SOP 调用栈
```

每个栈帧的结构：

```python
{
    "sop_id": "GIT_SMART_COMMIT",          # 当前 SOP 标识
    "sop_plan_steps": "...",               # 当前 SOP 的 Plan_Steps（含进度标记）
    "sop_objective": "...",                 # 当前 SOP 目标
    "sop_retry_limit": 3,                   # 当前 SOP 重试上限
    "sop_tools_required": "get_git_diff,...",  # 当前 SOP 工具过滤
    "entry_step_number": 4,                # 从父 SOP 的哪个步骤进入的
    "return_step_number": 4,               # 执行完毕后回到父 SOP 的哪个步骤
    "return_variable": "VAR_sub_result",   # 子 SOP 结果存入的变量名
    "local_state": {                       # 子 SOP 局部状态（与父 SOP 隔离）
        "current_tool_call": "",
        "current_tool_call_raw": "",
        "current_tool_args": {},
        "execution_result": "",
        "last_step": "",
        "task_status": "ONGOING",
    }
}
```

#### 执行流程

```
父 SOP Plan_Steps:
  1. 调用 get_git_status()
  2. 调用 get_git_branches()
  3. 调用 GIT_BRANCH_CLEANUP()    ← CALL_SOP
  4. FINISH 分支清理已完成。

执行到步骤 3 时：

1. Scheduler 检测到步骤 3 是 CALL_SOP 类型
2. Push：将当前父 SOP 状态压入调用栈
3. Load：加载子 SOP (GIT_BRANCH_CLEANUP) 的 Plan_Steps
4. Execute：子 SOP 在自己的上下文中完整执行（多轮 Scheduler → ToolExecutor → ProgressUpdater）
5. Result：子 SOP 执行完毕（FINISH/ERROR）
6. Pop：从调用栈弹出，恢复父 SOP 状态
7. 将子 SOP 的执行结果写入 VAR_sub_GIT_BRANCH_CLEANUP_result
8. ProgressUpdater 在父 SOP 步骤 3 处追加 "子SOP已完成: 清理了3个过期分支..."
9. Scheduler 继续执行父 SOP 步骤 4
```

### 图结构变更

当前图是固定的 3 节点循环（Scheduler → ToolExecutor → ProgressUpdater → Scheduler）。子 SOP 需要**递归复用同一图结构**：

```
                    ┌────────────────────┐
                    │ SopExecutionScheduler │
                    └──────┬─────────────┘
                           │
                    ┌──────▼──────────────┐
              ┌─────│   路由判断           │
              │     └──────┬──────────────┘
              │            │
              │   ┌────────┼────────────┐
              │   │        │            │
              │   │ ONGOING│ CALL_SOP   │ FINISH/ERROR/INTERRUPT
              │   │        │            │
              │   ▼        ▼            ▼
              │ ┌──────┐ ┌──────────┐  ┌──────────┐
              │ │Tool  │ │Push +    │  │Pop (若栈 │
              │ │Exec  │ │Load子SOP │  │非空则恢复│
              │ │      │ │          │  │父SOP)    │
              │ └──┬───┘ └────┬─────┘  └────┬─────┘
              │   │           │              │
              │   ▼           │              │
              │ ┌──────┐      │              │
              │ │Prog  │      │              │
              │ │Update│      │              │
              │ └──┬───┘      │              │
              │   │           │              │
              │   └─────┬─────┘              │
              │         │                    │
              │         ▼                    │
              │  回到 Scheduler              │
              └──────────────────────────────┘
```

关键变更：
- 路由函数 `route_after_scheduler` 新增 `task_status == "CALL_SOP"` 分支
- 新增 `sop_stack_manager` 纯代码节点：处理 Push/Pop 操作 + 子 SOP 加载 + 变量作用域切换
- Scheduler → StackManager → Scheduler（不经过 ToolExecutor，因为子 SOP 调用本身不需要工具执行）

### 子 SOP 的结果返回

子 SOP 执行完毕后，其最终状态（FINISH/ERROR/INTERRUPT）和最终执行结果被压缩为一个返回值，写入父 SOP 的上下文：

```python
def _build_sub_sop_result(sub_state: dict) -> dict:
    """从子 SOP 执行完毕后的状态构建返回值。"""
    return {
        "status": sub_state["task_status"],        # FINISH / ERROR / INTERRUPT
        "summary": sub_state.get("execution_result", ""),  # 最终执行结果
        "detail": sub_state.get("final_report", ""),          # 子SOP的最终报告（存入变量）
    }
```

这个返回值遵循工具合约的三字段格式（`status/summary/detail`），因此父 SOP 的 ProgressUpdater **无需修改**即可处理子 SOP 返回结果——子 SOP 在父 SOP 看来就是一个特殊的"工具调用"。

### ProgressUpdater 变更

ProgressUpdater 新增第五种更新模式 `_update_call_sop`：

```python
def _update_call_sop(step: dict, sub_sop_id: str, status: str,
                     summary: str, detail_var: str):
    """为 CALL_SOP 步骤追加子 SOP 执行结果标记。"""
    formatted = _format_result(status, summary, detail_var)
    base = re.sub(r'\s*已跳过.*$', '', step['header'])
    step['header'] = f"{base} 子SOP[{sub_sop_id}] 结果: {formatted}。"
    step['sub_lines'] = []
```

父 SOP 的步骤 3 在子 SOP 执行完毕后变为：
```
3. 调用 GIT_BRANCH_CLEANUP() 子SOP[GIT_BRANCH_CLEANUP] 结果: 成功 | 已删除3个过期分支 | 变量: VAR_sub_GIT_BRANCH_CLEANUP_result。
```

用户通过查看父 SOP 的进度，能看到子 SOP 的执行摘要——不需要展开子 SOP 的每一步。

### 变量作用域：分层隔离 + 选择性传递

子 SOP 拥有独立的变量命名空间：

```
全局 VariableStore:
  VAR_get_git_diff (父 SOP 步骤 1 产出)
  VAR_get_git_log (父 SOP 步骤 2 产出)
  VAR_sub_GIT_BRANCH_CLEANUP_result (子 SOP 返回结果)
  
子 SOP GIT_BRANCH_CLEANUP 内部：
  可以读取父 SOP 的变量（通过 VAR_ 引用）
  子 SOP 内部变量不与父 SOP 冲突（如 VAR_get_git_log 在子 SOP 中也可以产出，但存入子 SOP 命名空间）
```

子 SOP 可以**读取但不修改**父 SOP 的变量。这种单向数据流（父 → 子只读，子 → 父仅通过返回值）防止了跨 SOP 的变量污染。

### SopSpecChecker 新增校验规则

在现有 13 项校验基础上新增规则 14-17：

| # | 规则 | 违规行为 |
|---|------|---------|
| 14 | CALL_SOP 引用的 SOP_ID 必须在 `sops.csv` 中存在 | 子 SOP 名拼写错误 |
| 15 | 不能自引用（SOP 不能调用自己） | SOP A 的 Plan_Steps 中调用 SOP A |
| 16 | 不能循环引用（A→B→A） | 加载时做静态依赖图分析 |
| 17 | 嵌套深度不能超过 `max_sop_depth`（默认 3） | 四层嵌套可能导致栈溢出和上下文膨胀 |

循环引用检测算法（加载时静态分析）：

```python
def detect_circular_reference(sop_id: str, all_sops: dict, 
                               visited: set, stack: list) -> list[list[str]]:
    """检测从 sop_id 出发的所有循环引用路径。
    返回所有检测到的环的列表。
    """
    cycles = []
    if sop_id in stack:
        cycle_start = stack.index(sop_id)
        cycles.append(stack[cycle_start:] + [sop_id])
        return cycles
    if sop_id in visited:
        return cycles
    
    visited.add(sop_id)
    stack.append(sop_id)
    
    plan_steps = all_sops.get(sop_id, {}).get("plan_steps", "")
    for sub_id in _extract_call_sop_ids(plan_steps):
        cycles.extend(detect_circular_reference(sub_id, all_sops, visited, stack))
    
    stack.pop()
    return cycles
```

### 深度限制与上下文预算

默认最大嵌套深度为 3 层。原因：
- 每层子 SOP 需要维护独立的局部状态（栈帧），深度过大会导致 state dict 膨胀
- 子 SOP 的 Thinker 推理需要理解父 SOP 的上下文——层数越多，上下文越复杂
- 实际使用中，3 层足够表达绝大多数任务（主任务 → 子任务 → 原子操作）

配置项：
```json
{
    "max_sop_depth": 3
}
```

### 子 SOP 的 user_instruction 自动生成

当父 SOP 调用子 SOP 时，子 SOP 的 `user_instruction` 被自动生成为参数化描述：

```
父 SOP 步骤 3: 调用 GIT_BRANCH_CLEANUP()
→ 子 SOP user_instruction: "执行 GIT_BRANCH_CLEANUP"
```

这个自动生成的 instruction 出现在子 SOP 的 Scheduler Thinker 输入中，让子 SOP 知道自己被调用的上下文。

### Scheduler 的路由逻辑变更

当前 `route_after_scheduler` 只检查 `task_status == "ONGOING"` 来决定是执行工具还是结束。变更后增加 CALL_SOP 分支：

```python
def route_after_scheduler(state: OverallState):
    status = state.get("task_status", "ONGOING")
    
    if status == "CALL_SOP":
        return "sop_stack_manager"       # Push + Load 子 SOP
    elif status == "ONGOING":
        # 检查当前步骤是否为 CALL_SOP 类型
        current_step = state.get("last_step", "")
        step_type = _classify_step(current_step)
        if step_type == StepType.CALL_SOP:
            return "sop_stack_manager"   # 同上
        return "tool_executor"
    elif status in ("FINISH", "ERROR", "INTERRUPT"):
        # 检查调用栈：若栈非空则 Pop 恢复父 SOP
        call_stack = state.get("sop_call_stack", [])
        if call_stack:
            return "sop_stack_manager"   # Pop + 恢复父 SOP
        return END
```

### 终端用户视角

子 SOP 嵌套对终端用户透明。用户只看到：
- 父 SOP 的进度面板逐步更新
- 当子 SOP 执行时，状态栏显示当前正在执行的子 SOP 名称
- 子 SOP 执行完毕后，父 SOP 继续
- 最终报告是父 SOP 的结果，可以展开查看子 SOP 的详细执行过程（通过日志文件）

---

## 为什么这么做

### 函数是程序员最熟悉、最可靠的组合抽象

编程语言用函数调用实现了任意复杂度的程序。一个 `main()` 调用 `parse_args()` → `validate_input()` → `process_data()` → `generate_output()`，每一层只关注自己的职责，通过参数和返回值通信。

SOP 嵌套模仿了完全相同的抽象：一个 SOP 就是一个函数，`CALL_SOP` 就是函数调用，参数传递和返回值就是函数签名。程序员（SOP 作者）不需要学习新的范式——他们已经在用这个思维模型了。

### 组合优于复制

没有子 SOP，如果 `GIT_SMART_COMMIT` 和 `GIT_PR_CREATE` 都需要 "收集 Git 状态" 这个步骤序列，只能复制粘贴到两个 SOP 的 Plan_Steps 中。问题：
- 修改时需同步更新两处（容易漏）
- 步骤序列本身没有命名（不知道这段步骤 "是什么"）
- 增加了每个 SOP 的步骤数量（更长 = 更难调试）

有了子 SOP，"收集 Git 状态" 被封装为一个独立的 `GIT_COLLECT_STATUS` SOP，两个父 SOP 只需一行 `调用 GIT_COLLECT_STATUS()`。

### 渐进复杂度：简单 SOP 仍保持简单

CALL_SOP 的引入不强制所有 SOP 使用嵌套。一个只有 4 个工具的简单 SOP 仍然可以写成平铺的 Plan_Steps。嵌套是可选的——当你需要它时才使用它。这保持了框架的易上手性。

### 调用栈让每个子 SOP 拥有独立的执行上下文

如果不使用栈，而是把所有状态平铺在 state dict 中（如 `sub_sop_tools_required`、`sub_sop_plan_steps` 等），那么：
- 每个嵌套层级需要一组命名约定（`sub_sop_xxx`、`sub_sub_sop_xxx`...）→ state 字段爆炸
- 子 SOP 完成后，父 SOP 的原始状态已被覆盖 → 无法恢复
- 嵌套深度被硬编码在字段名称中 → 不支持动态深度

调用栈是经过数十年编程语言实践验证的正确抽象——一个 `list[dict]` 干净地解决了所有这些问题。

### 变量作用域单向隔离防止跨 SOP 变量污染

如果子 SOP 可以写入父 SOP 的变量命名空间：
- 子 SOP 内部的 `VAR_get_git_status` 会覆盖父 SOP 的同名变量
- 父 SOP 在子 SOP 执行后读取 `VAR_get_git_status`，得到的是子 SOP 的结果而非自己期望的值
- Bug 的来源从 "当前 SOP 的某个步骤" 扩展到 "任意子 SOP 的任意步骤"——调试范围爆炸

单向数据流（父 → 子只读，子 → 父仅通过返回值）是经过实践检验的安全模式。函数式编程、React 单向数据流、Rust 的所有权系统——都指向同一个结论：**限制数据修改方向能消除一整类 bug。**

### 加载时循环引用检测 = 编译期检查

循环引用（A 调用 B，B 调用 A）是图结构问题，应该在 SOP 加载时静态检测，而非运行时发现。运行时发现意味着执行已经进入循环——等到检测出来时（嵌套深度超限），已经浪费了大量 LLM 调用和工具执行。

静态检测只需要加载所有 SOP 的 Plan_Steps 并提取 `CALL_SOP` 引用边，构建有向图做 DFS——这是 O(V+E) 的经典算法，加载时多花几毫秒即可。

### 子 SOP 结果遵循工具三字段契约让 ProgressUpdater 无需修改

设计决策：子 SOP 返回结果采用与工具调用相同的三字段格式（status/summary/detail）。这意味着 ProgressUpdater 的 `_update_call_sop` 可以直接复用 `_format_result` 和现有的格式化逻辑——不需要为子 SOP 单独写一套进度标记格式。

这也是为什么 `parsers/sop_plan.py` 中 `CALL_SOP` 的优先级在 CONDITIONAL 之前——子 SOP 调用可以在条件分支中出现（`如果日报生成成功，就调用 GIT_SMART_COMMIT`），而条件分支内的子 SOP 的进度更新逻辑和普通工具完全一致。

---

## 不这么做会怎样

### 继续用多个独立 SOP 手动串联

用户说 "整理今天的工作，生成日报，然后提交"：
- 当前：用户说 → Agent 匹配 GIT_BRANCH_CLEANUP → 执行 → 完成 → 用户再说 "帮我提交" → Agent 匹配 GIT_SMART_COMMIT → 执行
- 嵌套 SOP 下：用户说一句话 → Agent 匹配顶层 SOP → 顶层 SOP 自动调用清理子 SOP → 清理完成后继续提交子 SOP → 一气呵成

前者需要用户记住 "日报做完了，现在要提交"，后者是一次交互。对于长任务来说，中间的上下文切换（用户在日报完成和提交开始之间等待）是高频的痛点。

### 把长 SOP 写成超长 Plan_Steps

不用嵌套，把所有子步骤平铺到一个 SOP 中。一个 "完整系统诊断 + 修复" SOP 可能有 30+ 步骤。

问题：
- 30 步的 Plan_Steps 在每次 Scheduler Thinker 调用时都被放入 prompt → token 消耗巨大
- 条件分支嵌套变得难以阅读（步骤 12 的条件分支影响步骤 20 的行为——中间 8 个步骤都是分支的一部分？）
- 某个子流程需要修改（如日志分析逻辑调整）→ 需要在一个 30 步的 SOP 中找到对应的步骤 → 容易误改其他步骤
- SopSpecChecker 的步骤连续性校验（规则 10）在大 SOP 中更容易触发误报

### 变量作用域全局共享

所有变量存在一个全局 dict 中，没有命名空间隔离。子 SOP A 和子 SOP B 都产出了 `VAR_get_git_status`，后执行的会覆盖先执行的——但父 SOP 期望分别引用两者。

结果：每次加新的子 SOP 都需要审计它产出的所有变量名，确保不与任何已有 SOP 冲突。这在实际使用中不可扩展——SOP 作者需要知道整个项目中所有其他 SOP 的变量命名才能安全地开发。命名空间隔离是扩展性的前提。

### 不做循环引用检测

SOP A 调用 SOP B，SOP B 调用 SOP A → 运行时进入无限嵌套循环 → 直到 `max_sop_depth` 被触发才终止 → 此时已经浪费了大量 LLM 调用和 token。

更隐蔽的情况：A → B → C → A（三节点循环）。SOP 作者在编写时可能完全没意识到这个间接循环的存在（因为 A 和 C 是不同人编写的）。静态检测在加载时就报告 `检测到循环引用: GIT_BRANCH_CLEANUP → GIT_SMART_COMMIT → GIT_BRANCH_CLEANUP`——SOP 作者在看到这条报错时立刻明白了问题所在。

### 嵌套深度不做限制

理论上允许无限嵌套：A → B → C → D → E → ...。但每个嵌套层级带来：
- 新的局部状态（栈帧内存）
- 新的 Scheduler Thinker 上下文（需要理解自己在第 N 层）
- 子 SOP 返回时父 SOP 的状态恢复开销

3 层的默认限制覆盖了绝大多数实际需求（任务 → 子任务 → 原子操作），同时为状态管理和上下文预算提供了确定性边界。如果用户确实需要更深嵌套，可以通过配置项调整——但默认限制让新用户不至于意外触发深度递归。
