# UserCoordinator — 人机协作网关

## 做了什么

UserCoordinator 是 REPL 外层的 LLM 节点，负责在用户指令和执行引擎之间建立一道可控的"安全闸门"。它做三件事：

**意图分类**：每轮将用户输入分为 CHAT（闲聊）、UNCERTAIN（模糊任务）、EXECUTE（明确可执行任务）三类。存疑时优先归为 CHAT 或 UNCERTAIN——宁可多问一句，也不错判执行。

**三级渐进式确认**：当意图为 EXECUTE 时，系统不直接执行，而是跨多轮对话逐步收敛——Stage 1 匹配 SOP 并请求确认，Stage 2 细化缺失信息（时间范围、目标目录等）并提供默认值，Stage 3 展示完整摘要（LONG_TERM_INTENT）等待最终确认。

**IS_EXECUTE 闸门**：LLM 输出 `IS_EXECUTE="true"` 只是"建议执行"。真正的执行权在 `main.py` 的这段代码：

```python
if state.get("is_execute") == "true":
    confirm = input("\n确认执行? (y=执行 / n=重新规划): ")
    if confirm.lower() != 'y':
        continue  # 不执行
```

Validator 在 LLM 输出后、代码路由前做白名单校验：`IS_EXECUTE="true"` 时 SOP_ID 必须存在于 `sops.csv` 中，LONG_TERM_INTENT 必须非空。校验失败最多重试 3 次，仍失败则回退为安全默认值（道歉 + 请求澄清）。

## 为什么这么做

4B 模型可能产生幻觉——编造不存在的 SOP_ID、在用户未确认时输出 `IS_EXECUTE="true"`。如果直接信任 LLM 输出，一次幻觉就可能导致错误操作。把闸门做成代码硬开关（字符串比对 `== "true"`），意味着 LLM 只能"建议"、代码才"决定"——LLM 的随机性被隔离在闸门之前。

三级确认的设计逻辑是：用户不需要一次性想清楚所有细节。系统逐步引导——先确认任务对不对，再确认参数全不全，最后确认要不要执行。每一步用户都可以打断、修正或退出。

## 不这么做会怎样

AutoGPT 式自主 Agent 从用户意图直接跳到执行：Agent 说"我来帮你清理磁盘"然后直接 `rm -rf`。没有确认环节，没有闸门，行为不可审计。UserCoordinator 的三级确认 + IS_EXECUTE 硬开关，确保在用户明确说"y"之前，Agent 不能执行任何操作。
