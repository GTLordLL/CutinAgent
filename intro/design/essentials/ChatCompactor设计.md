# ChatCompactor — 对话上下文压缩

## 做了什么

ChatCompactor 是负责 **压缩对话上下文** 的 LLM 节点。当 REPL 中的原始对话（`current_dialogue`）积累过多导致 token 用量接近 8K 窗口上限时，ChatCompactor 将冗长的多轮对话压缩为 2-5 句密集摘要，追加到 `conversation_history` 并清空 `current_dialogue`，防止上下文溢出。

它是"对话压缩器"，与 TaskCompactor（执行压缩器）分工协作，共同管理 4B 模型的 8K 上下文窗口。

---

## 1. ChatCompactor 与 TaskCompactor 的区分

| 维度 | TaskCompactor | ChatCompactor |
|------|--------------|---------------|
| **触发时机** | 每次 SOP 执行完成后 | 手动 `/compact` 或 token > 4096 自动触发 |
| **压缩对象** | 本次 SOP 执行结果 + 本轮对话 | 当前对话缓冲区（`current_dialogue`） |
| **输出字段** | 3 字段：EVALUATION + CONVERSATION_SUMMARY + EXECUTION_SUMMARY | 1 字段：CONVERSATION_SUMMARY |
| **输入上下文** | USER_MESSAGE + CURRENT_DIALOGUE + CONVERSATION_HISTORY + CURRENT_ACTION + LONG_TERM_INTENT + EXECUTION_HISTORY + LATEST_EXECUTION_RESULT | COMPACT_REQUIREMENT + USER_MESSAGE + CURRENT_DIALOGUE + CONVERSATION_HISTORY |
| **Validator** | `CompactorValidator`（三字段校验） | `ChatCompactorValidator`（单字段校验） |
| **运行位置** | SOP 图执行后，用户满意度确认前 | 可在 REPL 循环中任意时刻触发 |
| **输出写入** | `conversation_history` + `execution_history` | 仅 `conversation_history` |

> **两者都是闭包工厂，不注册为 LangGraph 图节点。** 它们关注的是"跨 SOP 周期"的信息管理，不受图执行循环（Scheduler → ToolExecutor → ProgressUpdater）的约束。

---

## 2. 触发方式

### 2.1 手动触发（`/compact` 命令）

用户在 REPL 中输入 `/compact [提示]`，可附带压缩要求（如"刚才的废话不重要"、"重点保留 git 提交需求"）。

```python
# command_handler.py
if name == "/compact":
    requirement = " ".join(parts[1:]) if len(parts) > 1 else ""
    state["chat_compact_requirement"] = requirement
```

`requirement` 作为 `COMPACT_REQUIREMENT` 传入 Thinker prompt，引导压缩方向。

### 2.2 自动触发（token 阈值）

UserCoordinator 每轮返回后，main.py 检查上一轮 Thinker 的输入 token 数：

```python
if state.get("thinker_input_tokens", 0) > 4096 and state.get("current_dialogue", "").strip():
    # 自动压缩
```

阈值设为 4096（8K 窗口的 50%），确保留有足够空间给本轮 Thinker + Formatter 的推理链和 SOP 执行。

---

## 3. Thinker + Formatter 双阶段设计

与其他 LLM 节点一致，ChatCompactor 采用 Thinker（temp 0.4）+ Formatter（temp 0.0）架构。

### 3.1 Thinker 输入构造

ChatCompactor Thinker 仅接收对话相关的上下文（不涉及 SOP 执行状态）：

```
COMPACT_REQUIREMENT: {用户的压缩提示 或 "None"}
USER_MESSAGE: {用户最新消息}
CURRENT_DIALOGUE: {自上次压缩以来的原始对话}
CONVERSATION_HISTORY: {已有的对话摘要历史}
```

### 3.2 Thinker 推理流程（3 步）

1. **解读压缩指引**：如果 `COMPACT_REQUIREMENT` 非空，按用户要求引导信息取舍；如果为 "None"，使用默认平衡策略
2. **从 CURRENT_DIALOGUE 提取关键信息**：保留目标、约束、偏好、决策、方向性反馈；丢弃闲聊、重复澄清、寒暄
3. **与 CONVERSATION_HISTORY 合并**：不简单拼接已有摘要，而是将新信息无缝整合到已有历史中，避免冗余

### 3.3 Formatter 单字段提取

Formatter (temp 0.0) 只提取一个结构化字段：

```
CONVERSATION_SUMMARY: <2-5句密集对话摘要>
```

### 3.4 重试与 Fallback

- Formatter 校验失败 → 错误信息追加到 prompt → 重试（最多 3 次）
- 3 次全失败 → 硬编码英文 fallback：`"User conversation occurred but could not be summarized."`

---

## 4. 输出字段

| 字段 | State 键名 | 含义 |
|------|-----------|------|
| `CONVERSATION_SUMMARY` | `state["chat_conversation_summary"]` | 2-5 句对话摘要，合并了 CURRENT_DIALOGUE 的关键信息 |

输出后，main.py 代码将其追加到 `conversation_history` 并清空 `current_dialogue`：

```python
if summary:
    state["conversation_history"] += "\n" + summary
    state["current_dialogue"] = ""
```

---

## 5. Validator

`validator/ChatCompactorValidator.py` 的 `validate_chat_compactor_output()` 校验：

1. 解析 `CONVERSATION_SUMMARY:` 字段（正则匹配）
2. 截断防止字段值穿越到后续标签（`cut_markers` 机制）
3. 非空 / 非 "NONE" 检查

---

## 6. 配置项

| 配置键 | 温度 | 说明 |
|--------|------|------|
| `chat_compactor_thinker` | 0.4 | ChatCompactor Thinker 专用 LLM |
| `all_formatter` | 0.0 | 共享 Formatter（与 UserCoordinator、Scheduler、TaskCompactor 共用） |

ChatCompactor Thinker 有独立的 LLM 实例（通过 `resources.get_llm("chat_compactor_thinker")` 获取），Formatter 使用共享的 `all_formatter` 实例。

---

## 7. Prompts

### Thinker prompt（`prompts/chat_compactor/thinker.md`）

3 步推理引导：
1. 解读压缩指引（有/无用户指导）
2. 从 CURRENT_DIALOGUE 提取关键信息（保留 vs 丢弃）
3. 与 CONVERSATION_HISTORY 合并（消除冗余）

正面引导："保留什么"、"如果已有历史则无缝合并"，而非"不要重复"、"不要丢失信息"。

### Formatter prompt（`prompts/chat_compactor/formatter.md`）

单字段提取模板 + 2 个示例（带压缩指导 / 自动压缩无指导）。

---

## 8. 生命周期

```
用户对话累积 → current_dialogue 增长
    │
    ├─ 手动 /compact → ChatCompactor 压缩 → CONVERSATION_SUMMARY
    │                                          ↓
    │                              追加到 conversation_history
    │                              current_dialogue = ""
    │
    └─ token > 4096 自动触发 → ChatCompactor 压缩 → (同上)

SOP 执行 → TaskCompactor → CONVERSATION_SUMMARY + EXECUTION_SUMMARY
                                ↓
                  conversation_history += CONVERSATION_SUMMARY
                  execution_history += EXECUTION_SUMMARY
                  current_dialogue = ""
```

**关键区别**：ChatCompactor 只操作 `conversation_history`（不加 `execution_history`），因为它在 SOP 执行之外运行，没有执行上下文可总结。

---

## 9. 为什么这么做

### 4B 模型 8K 上下文 —— 不压缩必然溢出

qwen3:4b 虽然被定制扩展为 8K 上下文窗口，但一个典型的 SOP 执行周期中：SOP Plan_Steps ~500-1000 tokens，每轮工具调用结果 ~200-500 tokens，CURRENT_DIALOGUE ~500-2000 tokens，叠加 HISTORY 累积和 Thinker prompt。3-4 轮 SOP 执行后总 token 轻松超过 8K。ChatCompactor 在 token 接近危险水位线（4096 / 50%）时提前压缩对话，为后续 SOP 执行保留足够空间。

### 对话压缩与执行压缩分离

对话和理解用户意图是**人机协作**的核心，对话摘要 (`conversation_history`) 需要跨 SOP 周期保留用户意图链。而执行摘要 (`execution_history`) 记录的是"做了什么"——把两者混在一起压缩会丢失"谁说了什么"的边界，降低 UserCoordinator 的意图匹配准确率。分开压缩保留了信息源标签。

### ChatCompactor 在 REPL 循环中而非 SOP 图内

对话积累在 SOP 图执行之外（图只处理工具调用和进度更新）。如果把 ChatCompactor 放在图内作为节点，每次工具调用循环后都会触发压缩——但大部分时候对话没有新增内容，压缩是空转。作为 REPL 外层的独立调用更合理：对话积累到需要压缩时才压缩。

### `/compact` 允许用户指导压缩方向

用户通过 `/compact 刚才的废话不重要` 可以告诉压缩器侧重保留什么。这利用了人对"什么重要"的判断力，比纯自动压缩更精确。自动触发时 `COMPACT_REQUIREMENT` 为 `None`，使用默认平衡策略。

### 阈值设为 4096 而非 8192

50% 的保守阈值有两个原因：
1. 压缩本身需要时间（Thinker + Formatter ~5-15s），如果在 7900 tokens 时触发，压缩过程中可能已经溢出
2. 压缩后的摘要需要追加到 Thinker 输入中，加上本轮推理链和 Formatter 输出，需要 ~3000-4000 tokens 的余量
