# Compactor — 历史压缩与长期记忆

## 做了什么

Compactor 是 SOP 执行完毕后运行的 LLM 节点，负责三件事：

**评价执行结果**：输出 `EVALUATION`（1-2 句），判断本次 SOP 是否达成 `CURRENT_ACTION` 的目标。

**压缩对话历史**：输出 `CONVERSATION_SUMMARY`（2-4 句），从 `CURRENT_DIALOGUE` 中提取对长期意图必要的内容——目标、约束、决策——丢弃闲聊和精确措辞。

**压缩执行历史**：输出 `EXECUTION_SUMMARY`（2-4 句），保留结论、关键发现、后续 SOP 可能需要的数据点，丢弃原始工具输出和详细日志。

**生命周期由代码管理**——这是关键。`main.py` 中的逻辑：

```python
if satisfied.lower() == 'y':
    state["conversation_history"] += "\n" + state["compactor_conversation_summary"]
    state["execution_history"] += "\n" + state["compactor_execution_summary"]
    state["current_dialogue"] = ""  # 满意后才清除
```

LLM 只负责生成摘要文本（它擅长的事）。代码决定何时追加到长期记忆、何时清除对话——这些是状态生命周期决策，需要确定性。

## 为什么这么做

qwen3:4b 的上下文窗口仅 8K tokens（从默认 2K 定制扩展）。多轮 Agent 对话中，SOP 计划 + 工具结果 + 对话记录持续膨胀。不做压缩的话，3-4 轮 SOP 执行后窗口塞满，模型开始截断——丢失的不是冗余信息，而是关键的上下文（当前执行到哪一步、用户最初的需求是什么）。

Compactor 让摘要跨 SOP 周期累积：`CONVERSATION_SUMMARY` 串起来形成"用户长期意图链"，`EXECUTION_SUMMARY` 串起来形成"操作历史链"。每轮只追加 2-4 句密集摘要而非完整原始文本，8K 窗口内可容纳的会话周期大幅延长。

代码管理生命周期同样重要。如果 LLM 决定何时清除对话——它可能在用户还不满意时就清除了上下文，导致后续调整缺乏依据。代码通过 `input("满意吗?")` 等待用户确认，满意才清除——这个决策不能交给随机模型。

## 不这么做会怎样

不做压缩 → 3-4 轮后上下文溢出 → 模型截断丢失当前执行状态 → Scheduler 不知道该执行哪一步 → 任务失败。LLM 管理生命周期 → 不满意时对话已被清除 → 用户说"不对，重新来"但上下文已丢失 → 无法纠正。
