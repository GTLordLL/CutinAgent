# TTS 语音播报 — Microsoft Edge TTS 云端引擎

## 做了什么

CutinAgent 集成了基于 Microsoft Edge TTS（edge-tts）的语音播报功能，将 Agent 的结论性回复通过语音朗读出来。用户无需盯着终端屏幕，可以在 Agent 执行任务期间处理其他事情。

### 引擎选型：edge-tts（云端推理，零本地开销）

选用 Microsoft Edge 免费 TTS API（`edge-tts` Python 库），而非本地推理方案（如 pyttsx3）。理由：
- **零 VRAM 开销**：合成在微软云端完成，不占用 RTX 3060 的 6GB 显存
- **音质自然**：神经网络语音（Xiaoxiao 等），远优于离线 TTS
- **原生 async**：`edge_tts.Communicate` 返回 awaitable，适配 REPL 的 asyncio 事件循环
- **多语音选择**：支持 8 种中文语音（男/女/方言），可通过 `/config` 切换

### 模块架构（`utils/tts_engine.py`）

| 函数 | 类型 | 职责 |
|------|------|------|
| `preload()` | async | 启动时验证 API 连通性（发送短合成请求），设置 `_ready` 标志 |
| `is_loaded()` | sync | 返回 TTS 服务是否可用 |
| `speak_async(text)` | async | 单次 TTS 合成 + ffplay 播放（edge_tts 合成 → mp3 → ffplay） |
| `tts_say(text)` | sync | 对外统一入口：TTS 开启时入队文本，支持主线程和 worker 线程 |
| `_tts_consumer()` | async | 后台消费者协程：从队列取文本，串行调用 `speak_async` |

### 播报队列（单消费者串行播放）

多次快速调用 `tts_say()` 时，文本进入 `asyncio.Queue`，由单一后台消费者协程（`_tts_consumer`）串行取出播放。这避免了多个 `ffplay` 进程同时运行导致的音频重叠。

```
tts_say("第一条消息")  →  Queue.put_nowait()
tts_say("第二条消息")  →  Queue.put_nowait()
                              ↓
                      _tts_consumer (单消费者):
                        await speak_async("第一条消息")
                        await speak_async("第二条消息")
```

消费者在空队列时阻塞在 `queue.get()`（零 CPU 开销），`speak_async` 中 `ffplay` 走 `run_in_executor`（释放事件循环）。

### 线程安全：双路径入队

`tts_say()` 是同步函数，支持从两个上下文调用：

- **主线程路径**：`asyncio.get_running_loop()` 成功 → 直接 `put_nowait` 入队
- **Worker 线程路径**：在 `run_in_executor` 的线程中调用 → `asyncio.run_coroutine_threadsafe` 调度到主事件循环入队

这确保了 LLM 执行线程（ThreadPoolExecutor worker）中也能触发播报。

### 启动流程：banner 前连通性检测

REPL 启动时，在 banner 输出之前执行连通性检测：

```
正在初始化 LLM 资源与知识库...
会话目录: ...
正在检测 TTS 服务连通性...        ← preload() 调用
TTS 语音服务已就绪。              ← _ready = True
                                   ← 如果失败：TTS 服务不可用，播报已自动关闭。

=================================================================
     ______         __   _          ___                      __
    ...（banner）
=================================================================
```

检测只在 TTS 配置开启时执行（`get_config().get("tts_enabled", False)`），关闭时不消耗启动时间。

### 播报触发时机

**播报**：Agent 的最终聊天回复（`chat_message`）——即 UserCoordinator 返回给用户的自然语言回复。

**不播报**：流式思考过程（Thinker 推理链、Formatter token 流）——这些是 dim 灰色文本，属于内部推理过程，朗读无意义且干扰。

```python
# main.py 中触发点
print_agent_message(console, state["chat_message"])
tts_say(state["chat_message"])  # 仅播报结论，不播报思考
```

### 配置集成

通过 `/config` 命令可调整 3 个 TTS 参数：

| 配置项 | 键名 | 默认值 | 说明 |
|--------|------|--------|------|
| TTS 语音播报 | `tts_enabled` | `True` | 总开关，关闭后不合成不播放 |
| TTS 语音 | `tts_voice` | `zh-CN-XiaoxiaoNeural` | 8 种中文语音可选（含方言） |
| TTS 语速 | `tts_rate` | `+0%` | -50% 到 +100%，步长 10% |

### 异常静默降级

TTS 的任何失败都不会影响 REPL 正常工作：
- `preload()` 失败 → `_ready = False`，`tts_say()` 直接返回
- `speak_async()` 失败 → `logger.debug` 记录，不抛异常
- `ffplay` 超时（60s）→ `subprocess.TimeoutExpired` 被捕获
- 临时 mp3 文件在 `finally` 块中清理

---

## 为什么这么做

### 云端推理而非本地 TTS

本地 TTS（pyttsx3 / espeak）音质机械、中文支持差、需要额外依赖。Microsoft Edge TTS 是神经网络语音，免费且不限量。云端推理不占用本地 GPU/CPU，对 4B 模型已经很紧张的显存零负担。

### 队列而非并行播放

如果每次 `tts_say()` 直接 `create_task(speak_async())`，多次快速调用会启动多个并发 `ffplay` 进程——音频重叠、互相干扰。单消费者队列保证了"说完一句再说下一句"的串行体验。

### 检测在 banner 前执行

如果把 TTS 检测放在 banner 之后，用户看到欢迎画面后还要等 2-3 秒才能看到"TTS 语音服务已就绪"——视觉上 banner 下方突然多出两行文字，布局显得不稳定。放在 banner 前输出，启动流程是一条线性信息流：初始化 → 会话目录 → TTS 检测 → 欢迎界面。

### 双路径线程安全

`run_in_executor` 的线程中无法直接操作 asyncio.Queue（不是事件循环线程）。`run_coroutine_threadsafe` 是 asyncio 提供的标准跨线程调度机制——将协程安全地投递到目标事件循环执行。

### 异常静默降级（不抛异常）

TTS 是"锦上添花"而不是核心功能。如果因为网络问题、ffplay 缺失、API 限流等导致 TTS 不可用，Agent 的对话和执行能力不应受任何影响。所有 TTS 异常都在内部捕获，对外表现为"什么都没发生"——用户体验是 Agent 正常回复，只是没有语音。

---

## 不这么做会怎样

### 无队列机制

多次快速 `tts_say()` → 多个 `ffplay` 进程同时播放 → 用户听到多条语音重叠在一起，完全无法理解。

### 不检测连通性

用户配置开启了 TTS，启动后 Agent 正常对话但没有语音（API 不通）。无从知道是配置问题、网络问题、还是功能未实现——排查困难。

### 检测在 banner 之后

```
=================================================================
    ...（banner 大块 ASCII 艺术）...
=================================================================
  正在检测 TTS 服务连通性...      ← banner 下方突然出现，视觉上"掉帧"
  TTS 语音服务已就绪。
```

banner 是视觉重心，检测信息放在之前形成连贯的启动信息流，放在之后则像是"忘了放，补上去的"。

### TTS 失败导致 REPL 崩溃

用户正在对话中，一次 TTS 网络超时 → `speak_async()` 抛异常未捕获 → REPL 崩溃 → 丢失当前会话进度。TTS 是可选功能，它的失败不应影响核心对话流程。
