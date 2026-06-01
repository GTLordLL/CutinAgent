# CutinAgent REPL UI 设计文档

终端里有三套样式各管一部分：

- Rich — 负责上方内容区域：dim 灰色流式输出、Panel 边框、Markdown 渲染、Text 样式
- prompt_toolkit — 负责底部固定区域的布局和样式：TextArea 输入框、FormattedTextControl
状态栏、Window(char="─") 分隔线
- ANSI 控制码 — patch_stdout 的 run_in_terminal 底层用来保存/恢复光标位置，这个是裸终端转义序列，不属于 Rich

简单说：上半屏是 Rich 的，下半屏（固定栏）是 prompt_toolkit 的。

## 1. 流式输出方案

| 方案 | 描述 | 状态 |
|------|------|------|
| A：同步阻塞 | LLM 完成后一次性输出 | 未采用 |
| B：全异步 token 级流式 | async/await 改造所有节点 | 未采用 |
| C：run_in_executor + 间隔缓冲 | 每 2s 批量输出 | **实际采用** |

核心思路：LLM 同步调用放到 ThreadPoolExecutor，主事件循环保持活跃让 patch_stdout 能定期
flush。buffer_interval=2.0 把写入频率从 ~100次/秒 降到 ~0.5次/秒，解决 patch_stdout
高频写入丢数据的问题。比方案 A 体验好（不用干等），比方案 B 改动小（不用 async化所有节点）。

---

## 2. 核心方案：Application(full_screen=False) + patch_stdout

### 2.1 原理

- Application(full_screen=False) — 不接管全屏，只管理底部 5 行的输入区域
- patch_stdout(raw=True) — 在 Application 活跃期间，所有 sys.stdout 写入被代理拦截，
  通过 ANSI 控制码渲染到 Application 上方的终端滚动区域
- Rich Console 的输出默认写入 sys.stdout，所以自动被 patch_stdout 路由到上方
- 输入区域始终由 Application 维护，不会消失

### 2.2 布局结构

```
[上方：终端原生滚动区域 — Rich 输出通过 patch_stdout 渲染到这里]
                                        ← Window(char=" ")      空行（视觉隔离）
────────────────────────────────────────  ← Window(char="─")   顶部分隔线
  > [用户输入区域]                        ← TextArea            用户输入
────────────────────────────────────────  ← Window(char="─")   底部分隔线
  CutinAgent REPL — /help 查看命令        ← FormattedTextControl 状态栏
```

Application 只占底部 5 行，其余终端区域供 Rich 输出自由使用。

### 2.3 顶部运行时状态栏

在执行 LLM 调用（UserCoordinator、ChatCompactor、SOP 图）期间，顶部动态显示实时耗时：

```
  UserCoordinator: 12s                                     ← 有运行时 → height=3
────────────────────────────────────────                    ← Window(char="─")
  > [用户输入区域]                                           ← TextArea
────────────────────────────────────────
  CutinAgent REPL — /help 查看命令                           ← 状态栏
```

**实现机制**：

- `top_status_data = {"runtime_text": ""}` — 可变字典，`FormattedTextControl` 通过闭包 lambda 引用
- `has_runtime = Condition(lambda: bool(top_status_data.get("runtime_text", "")))` — 动态控制高度
- 有运行时文本 → `ConditionalContainer` 显示 height=3 的状态行
- 无运行时文本 → `ConditionalContainer` 替换为 height=1 的空行
- 后台定时器（`_runtime_timer`）每 0.5s 更新一次 `runtime_text` 并调用 `app.invalidate()` 刷新

**计时器生命周期**：

```python
async def _runtime_timer(label, start_time, stop_event):
    while not stop_event.is_set():
        top_status_data["runtime_text"] = f"  {label}: {_fmt_elapsed(elapsed)}"
        app.invalidate()
        await asyncio.wait_for(stop_event.wait(), timeout=0.5)
```

LLM 调用完成后 → `stop_event.set()` → 定时器退出 → `runtime_text` 清空 → 顶部栏缩回 1 行空白。

### 2.4 Token 用量显示

底部状态栏第二行显示当前 Thinker 输入 token 数及占 8K 窗口的百分比：

```
────────────────────────────────────────
  CutinAgent REPL — /help 查看命令
                      1,234 (15.1%) tokens                      ← 右对齐
```

**实现机制**：

- `status_data["token_info"]` 字段存储格式化的 token 信息
- UserCoordinator 每轮返回后更新：

```python
input_tokens = state.get("thinker_input_tokens", 0)
ratio = (input_tokens / 8192) * 100
token_text = f"{input_tokens:,} ({ratio:.1f}%) tokens  "
status_data["token_info"] = token_text.rjust(shutil.get_terminal_size().columns)
```

- 右对齐使用 `str.rjust()` 填充到终端宽度，确保 token 数字始终在右下角
- `/clear` 和 `/resume` 恢复会话时将 token 显示重置为 `"0 (0.0%) tokens"`

### 2.5 布局结构（完整）

包含顶部运行时状态栏 + 两行底部状态栏的完整布局：

```
                                              ← Window(char=" ")      空行（顶部间距）
  UserCoordinator: 12s                        ← 运行时状态 (height=3)  仅 LLM 执行时显示
                                              ← Window(char=" ")      空行
────────────────────────────────────────      ← Window(char="─")      顶部分隔线
  > [用户输入区域]                             ← TextArea              用户输入
────────────────────────────────────────      ← Window(char="─")      底部分隔线
  CutinAgent REPL — /help 查看命令             ← FormattedTextControl  状态栏第1行
                      1,234 (15.1%) tokens     ← FormattedTextControl  状态栏第2行 (token)
```

Session Picker 激活时，底部替换为 8 行选择器（详见 4.1 节）。

---

## 3. Rich 样式体系

采用"灰色思考 → 正常结果"的视觉分层：

### 3.1 dim（灰色）— 思考过程

| 使用场景 | 实现方式 |
|----------|---------|
| Thinker/Formatter 流式 token | `Console.out(text, style="dim")` |
| 节点标签（"[Thinker]", "[Formatter]"） | `Console.out("  [Thinker] ", style="dim", end="")` |
| SOP 图节点 Panel 副标题 | `"[dim]{node_name}[/dim]"` |
| 系统提示信息 | `"[dim]正在初始化...[/dim]"` markup |

### 3.2 默认色 — 最终结果

| 使用场景 | 实现方式 |
|----------|---------|
| Agent 聊天回复 | `Console.print(Markdown(text))` |
| 命令结果（/help, /sops 等） | `Console.print(Markdown(text))` |
| 各类 Panel（确认、执行、完成、评价） | `Console.print(Panel(...))` |

### 3.3 强调样式

| 样式 | 使用场景 |
|------|---------|
| **bold** | 用户消息 `▌` 标记、欢迎标题、退出消息 |
| **bold red** | 错误消息（SOP 加载失败、执行崩溃） |
| **class:status** | prompt_toolkit 状态栏（终端主题决定，通常反色） |

### 3.4 设计原则

- Thinker/Formatter 的流式输出全程 dim，不干扰用户阅读
- 最终结构化结果用默认色 + Panel 包裹，与思考过程形成清晰对比
- 错误用红色粗体，确保用户不会错过

---

## 4. 模块架构

REPL UI 相关代码按运行时角色拆分到 `repl/` 目录：

| 模块 | 职责 | 关键函数/类 |
|------|------|------------|
| `main.py` | 编排层：资源初始化 → UI构建 → 工作流循环 | `run_repl()` |
| `repl/app_builder.py` | prompt_toolkit 组件工厂（纯 UI 基础设施） | `create_input_field`, `create_status_bar`, `create_root_container`, `create_layout`, `build_application` |
| `repl/ui_renderer.py` | Rich 渲染函数（纯展示逻辑） | `print_welcome`, `print_user_message`, `print_agent_message`, `print_command_result` |
| `repl/command_handler.py` | 命令分发 + Tab 补全 | `dispatch_repl_command`, `ReplCompleter` |
| `repl/sop_runner.py` | SOP 图执行 + 节点 Panel 渲染 | `run_sop_graph` |
| `repl/state_manager.py` | State 创建与重置 | `create_initial_state`, `reset_sop_state` |
| `repl/session_manager.py` | 会话 CRUD + 运行摘要 | `create_session_dir`, `save_session`, `load_session`, `list_sessions`, `write_run_summary` |
| `repl/session_picker.py` | 会话选择器渲染与交互 | `create_picker_state`, `create_picker_control`, `activate_picker`, `picker_select`, `picker_cancel` 等 |
| `utils/streaming.py` | LLM token 流式输出（含 buffer_interval 逻辑） | `stream_llm` |

依赖方向：`main.py` → `repl/*` → `utils/streaming`（编排层依赖基础设施层）。

### 4.1 会话选择器覆盖机制

`/resume`（无参数）触发时，会话选择器通过 `ConditionalContainer` 条件覆盖底部状态栏：

```
正常状态：                    选择器激活（picker_filter=True）：
  ─────────────────────           ─────────────────────
    输入区域 (TextArea)              输入区域 (TextArea)
  ─────────────────────           ─────────────────────
    状态栏 (height=2)        →      会话选择器 (height=8)
    [第1行]  [第2行]                 会话列表 (每页5条)
                                     ← → 上下 翻页/选择
```

**键位绑定（picker 激活时）**：

| 按键 | 操作 | 说明 |
|------|------|------|
| ↑ | `picker_move_up` | 上移高亮项 |
| ↓ | `picker_move_down` | 下移高亮项 |
| ← | `picker_page_left` | 翻到上一页 |
| → | `picker_page_right` | 翻到下一页 |
| Enter | `picker_select` | 确认选择，设置 `result_event` |
| Esc | `picker_cancel` | 取消选择，设置 `result_event` |

所有 picker 按键绑定的 `filter` 参数设为 `picker_filter & has_focus(input_field)`（方向键为 `picker_filter`），确保仅在选择器激活时生效，不影响正常 REPL 输入。

---

## 5. 线程模型

### 5.1 线程清单

| 线程 | 角色 | 说明 |
|------|------|------|
| **MainThread** | asyncio 事件循环 | 运行 `app.run_async()`，处理 prompt_toolkit 渲染和用户输入 |
| **patch-stdout-flush-thread** | daemon 线程 | patch_stdout 内部创建，每 ~120ms 将代理缓冲区通过 `run_in_terminal` 提交到主线程渲染 |
| **ThreadPoolExecutor worker** | LLM 调用线程 | 通过 `run_in_executor` 运行同步 LLM 调用（UserCoordinator、SOP 图、Compactor） |
| **Ollama HTTP threads** | httpx 内部线程 | ChatOllama 底层 HTTP 请求的线程池 |

### 5.2 协调流程

```
MainThread                        ThreadPoolExecutor          Ollama
    │                                    │                      │
    ├─ run_in_executor(user_coordinator) │                      │
    │  ─────────────────────────────────► │                      │
    │                                    │─ stream_llm() ──────►│
    │                                    │◄── token chunks ────│
    │                                    │  (每2s flush到stdout) │
    │◄─── result ─────────────────────── │                      │
    ├─ sleep(0.3) ← 等 patch_stdout      │                      │
    │             _flush_thread 渲染完毕  │                      │
    │                                    │                      │
    ├─ (用户确认，async Event 等待)       │                      │
    │                                    │                      │
    ├─ run_in_executor(run_sop_graph)    │                      │
    │  ─────────────────────────────────► │                      │
    │                                    │─ (Scheduler/Executor │
    │                                    │   /ProgressUpdater)  │
    │◄─── result ─────────────────────── │                      │
    ├─ sleep(0.3) ← 等 patch_stdout      │                      │
    │             _flush_thread 渲染完毕  │                      │
    │                                    │                      │
    ├─ run_in_executor(compactor)        │                      │
    │  ─────────────────────────────────► │                      │
    │◄─── result ─────────────────────── │                      │
    ├─ sleep(0.3) ← 等 patch_stdout      │                      │
    │             _flush_thread 渲染完毕  │                      │
```

关键点：LLM 调用在线程池中串行执行（每次只提交一个任务），主线程在 `await` 期间可处理
patch_stdout 的 flush 回调和用户输入事件。

核心修复：`stream_llm()` 最终 flush 后追加 `_write("\n")` 确保流式输出以换行结尾，
防止末行被后续 `console.print()` 覆盖。配合两层 `sleep(0.3)` 避免 `_flush_thread`
（0.2s 周期）将流式文本与后续 Rich 输出合并到同一 `run_in_terminal` 批次。

---

## 6. 确认流程

采用 `asyncio.Event` + 状态标记模式，替代 PromptSession.prompt_async()：

### 6.1 状态变量

- `flag_processing: bool` — 正在处理输入时拒绝新输入
- `flag_waiting_confirm: bool` — 当前 Enter 应路由到确认处理
- `confirm_event: asyncio.Event` — 阻塞等待用户输入
- `confirm_value: dict` — 传递用户输入的文本

### 6.2 Enter 键路由逻辑

```
Enter 按下
  ├─ flag_waiting_confirm?  → 将输入文本写入 confirm_value，set event
  ├─ flag_processing?       → 忽略输入
  └─ 正常输入               → 创建后台任务执行 _handle_input()
```

### 6.3 确认调用点

1. **执行确认**：UserCoordinator 返回 `is_execute=true` 后，询问 y/n/补充信息
2. **拒绝后重新规划**：用户输入 n，再等待一次输入获取新需求描述
3. **满意度确认**：Compactor 评价后，询问 y/n

---

## 7. 流式缓冲设计

### 7.1 问题

逐 token 调用 `sys.stdout.write()` + `sys.stdout.flush()`（~100次/秒）导致
patch_stdout 代理缓冲区溢出，部分 token 丢失。

### 7.2 方案

`stream_llm()` 新增 `buffer_interval` 参数，默认为 2.0 秒。token 先累积到内存，
每隔 N 秒将新增部分批量写入 stdout，写入频率降至 ~0.5次/秒。

### 7.3 `_write()` 双路径

```python
def _write(text: str):
    if console and style:
        console.out(text, style=style, end="")  # Rich dim 样式
        console.file.flush()
    else:
        sys.stdout.write(text)                   # 无样式 fallback
        sys.stdout.flush()
```

- 有 console + style：走 Rich `Console.out()`，支持 dim 等样式
- 无 console/style：走原始 `sys.stdout.write()`，向后兼容

### 7.4 相关参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `buffer_interval` | 2.0 | 批量写入间隔（秒） |
| `console` | None | Rich Console 实例 |
| `style` | "" | Rich 样式字符串（如 "dim"） |
