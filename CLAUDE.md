# CLAUDE.md

请使用中文解释，高效场景（代码/提示词）使用英文。

**CutinAgent** — Python + LangGraph SOP 驱动型 Agent 框架，面向消费级硬件（RTX 3060 6GB）。

## 1. 目录职责

```
main.py                       # CLI/REPL 入口
cli/                          # Headless CLI (cutin run)
repl/
  execution/                  # 输入处理 → 分析员循环 → 协调器 → SOP 执行 → 压缩
  ui/                         # 按键绑定、布局、状态栏、命令提示
  commands/                   # / 命令分发、会话 CRUD
  state/                      # session / config / SOP state 持久化
  pickers/                    # 会话 / SOP / 配置 选择器 UI
graph/                        # LangGraph StateGraph 编译
llm_nodes/                    # 5 个 Thinker+Formatter 节点 + 双阶段运行器
data_nodes/                   # 非LLM: ToolExecutor, ProgressUpdater, VariableStore
parsers/                      # 纯文本解析，无副作用，不调 LLM
validator/                    # (bool, reason, parsed) 校验
tools/                        # ToolDispatcher + git_ops + linux_ops + prompts/
prompts/                      # 节点级 thinker/formatter markdown
sop/                          # SOP markdown (7 section) + sops.csv 索引
utils/                        # streaming, cancel_token, TTS, logger, sop_loader
user/                         # config/ (模型+运行时) + sessions/ (会话 JSON)
intro/design/                 # 设计文档: essentials/ + architecture/ + future/
```

## 2. 问题 → 文件速查

| 问题 | 文件 |
|------|------|
| 用户输入 → 分析员 → 协调器 → SOP 执行 全链路 | `repl/execution/input_handler.py` |
| SOP 执行流程（确认→加载→图→Compactor→满意度） | `repl/execution/execution_controller.py` |
| 按键绑定（Enter/Esc/Ctrl-C/↑↓） | `repl/ui/keybindings.py` |
| LLM 流式调用 + 取消令牌注入点 | `utils/streaming.py` + `utils/cancel_token.py` |
| 命令分发（/help /sops /config …） | `repl/commands/command_handler.py` |
| 会话 CRUD + 选择器交互 | `repl/commands/session_controller.py` + `repl/state/session_manager.py` |
| 配置管理（双层 + Copy-on-Activate） | `repl/state/config_manager.py` |
| Thinker+Formatter 运行器 + Validator 重试 | `llm_nodes/thinker_formatter_runner.py` |
| 工具路由分发 + VAR_ 变量解析 | `tools/ToolDispatcher.py` |
| LangGraph 图结构 + 路由 | `graph/Builder.py` |

## 3. 硬约束

- **依赖方向**: `nodes` → `parsers` + `validators`；`validators` → `parsers`。禁止反向。
- **parsers/**: 纯解析，无副作用，不调 LLM。validator/ 返回 `(bool, reason, parsed)`。
- **TUI**: `patch_stdout` 不可移除（输入栏锚定依赖）；流式 flush 末尾必须 `\n`；`full_screen=False`。
- **提示词**: 正面引导推理路径，不写打补丁式禁止。Thinker temp 0.4，Formatter temp 0.0。
- **取消**: `CancellationError` 是 `Exception` 子类，`except Exception` 会吞掉，需要时显式 `except CancellationError: raise`。

## 4. 运行

```bash
source .venv/bin/activate
cutin          # REPL
cutin run ...  # Headless
```

代理 `7897`（网络问题时）。
