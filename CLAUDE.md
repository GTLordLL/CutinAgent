# CLAUDE.md

请使用中文解释，需要高效率的地方(代码/提示词)使用英文。

## 1. 项目概述

**CutinAgent** 是一个基于 Python + LangGraph 的 **SOP 驱动型受控 Agent 框架**，专为消费级硬件（RTX 3060 6GB）设计。

> 架构设计详见 [架构概述](intro/design/architecture/架构概述.md)，完整论述见 [架构.md](intro/design/architecture/架构.md)

## 2. 开发规范

### 按函数在运行时的作用和功能归属模块，不要功能杂揉。

- **依赖方向**: `nodes` → `parsers` + `validators`；`validators` → `parsers`。禁止反向依赖
- **parsers/**: 纯文本解析，无副作用，不调 LLM
- **validator/**: 返回 `(bool, reason, parsed)` 的校验函数
- **llm_nodes/ data_nodes/**: LangGraph 节点编排，调用 parsers + validators
- 新增代码时，先判断属于哪一层，不要把所有逻辑堆在节点文件里
- **流式输出换行规则**：每次 flush 的文本末尾必须带 `\n`，否则光标不换行，
  下一次输出会覆盖当前行。标签使用 `Console.out()` 默认 `end="\n"` 即可
- **patch_stdout 不可移除**：`full_screen=False` 模式下，`patch_stdout` 的 `StdoutProxy`
  通过 `run_in_terminal` 在输出前保存光标、输出后恢复，这是 Application 输入栏
  固定在终端底部的关键。去掉后 Application 会随输出内容不断下移。即使 Rich Console
  输出可能部分绕过代理，`patch_stdout` 整体协调机制仍然保证布局稳定，不要去动它

### 提示词编写原则

**正面引导大模型如何推理，而非打补丁式约束。**

- 告诉模型"应该做什么、按什么步骤思考"，而不是"不要做X、禁止Y"
- 示例：对 SOP 匹配，用"基于已有 SOP_LIBRARY 描述你能处理的问题"引导，而非"不要编造不存在的 SOP"
- 每个意图分支显式要求输出格式（如 `Output CHAT_MESSAGE`），比事后校验更可靠
- Thinker prompt 的推理步骤本身就是一种引导式模板，模型沿着它走就不容易跑偏
- Formatter 不做创造性工作（temp 0.0），只做提取；Validator 做最后一道格式防线

### flush 末尾加 '\n'
patch_stdout 的 run_in_terminal 渲染机制：每次 flush后光标停留在输出文本末尾，不会自动换行。如果下一次 flush（或后续 Rich输出）从同一行开始写，必然覆盖当前行内容。

## 3. 关键设计

10 大设计要点的完整论述见 `intro/design/essentials/关键设计概述.md`，各要点详见独立设计文档：

| # | 设计要点 | 核心思路 | 设计文档 |
|---|---------|---------|---------|
| 3.1 | Thinker + Formatter 双阶段 | Thinker(temp 0.4)自由推理 + Formatter(temp 0.0)结构化提取 + Validator 重试兜底 | [ThinkerFormatter设计.md](intro/design/essentials/ThinkerFormatter设计.md) |
| 3.2 | UserCoordinator 人机协作网关 | 五字段输出 + 三级渐进确认 + IS_EXECUTE 代码闸门 | [UserCoordinator设计.md](intro/design/essentials/UserCoordinator设计.md) |
| 3.3 | Compactor 评价与历史压缩 | TaskCompactor(三字段)+ChatCompactor(单字段)双压缩体系 + 代码管理历史生命周期 + 8K 上下文防溢出 | [Compactor设计.md](intro/design/essentials/Compactor设计.md) / [ChatCompactor设计.md](intro/design/essentials/ChatCompactor设计.md) |
| 3.4 | SOP 存储与校验 | Markdown 7 section + 加载时 13 项校验 + CSV 轻量索引 | [SOP体系设计.md](intro/design/essentials/SOP体系设计.md) |
| 3.5 | 工具合约与变量传递 | 四字段统一契约 + 字典路由 + VAR_ 变量传递 + 采集-分析-判断闭环 | [工具合约设计.md](intro/design/essentials/工具合约设计.md) |
| 3.6 | 进度更新与重试 | 纯代码机械拼接 + 4 种追加模式 + 剥离-重建重试策略 | [进度更新与重试设计.md](intro/design/essentials/进度更新与重试设计.md) |
| 3.7 | 日志系统 | 按 round+node 分目录 + JSON 快照 + 文本日志互补 | [日志系统设计.md](intro/design/essentials/日志系统设计.md) |
| 3.8 | 图结构与路由 | 3 节点硬编码路由 + task_status 字符串比对 + ProgressUpdater 无条件回 Scheduler | [图结构与路由设计.md](intro/design/essentials/图结构与路由设计.md) |
| 3.9 | REPL UI 与流式输出 | Application(full_screen=False) + patch_stdout + buffer_interval 间隔缓冲 + Rich dim 样式分层 | [ui设计文档.md](intro/design/ui设计文档.md) |
| 3.10 | 会话管理系统 | Session JSON 7字段 + CRUD + 选择器(ConditionalContainer) + 自动保存/命名 + SOP ID 列表快照 | [会话管理设计.md](intro/design/essentials/会话管理设计.md) |
| 3.11 | 配置管理系统 | 两层配置 + Copy-on-Activate + 持久化 JSON + `/config` 选择器 UI + 6 个可配置项 | [配置管理设计.md](intro/design/essentials/配置管理设计.md) |

### 未来规划 (v0.2 / v0.3 RFC)

| # | 设计要点 | 核心思路 | 设计文档 |
|---|---------|---------|---------|
| F1 | 问题分析员 | UserCoordinator 前新增自主信息收集层，只读工具零确认调用，模仿 Claude Code"先理解后规划" | [问题分析员设计.md](intro/design/future/问题分析员设计.md) |
| F2 | 子SOP嵌套 | CALL_SOP 步骤类型 + 调用栈状态管理 + 变量作用域隔离，函数式组合长任务 | [子SOP嵌套设计.md](intro/design/future/子SOP嵌套设计.md) |

## 4. 目录结构

```
main.py                       # 入口：CLI/REPL 路由分发
pyproject.toml                # pip install -e .  + [project.scripts] 入口 cutin
cli/                          # Headless CLI (cutin run) — parser, runner, output formatter
repl/                         # REPL/TUI 基础设施 — 命令处理、会话、配置、UI渲染、执行控制
graph/                        # LangGraph StateGraph: Builder + OverallState TypedDict
llm_nodes/                    # LLM 节点 (Thinker+Formatter): UserCoordinator, Scheduler, Compactors
data_nodes/                   # 非LLM 节点: ToolExecutor, ProgressUpdater, VariableStore
parsers/                      # 纯文本解析，无副作用: sop_plan, tool_call
validator/                    # 校验函数 (bool, reason, parsed): SOP, Scheduler, Coordinator, Compactor
tools/                        # 工具系统
  ToolDispatcher.py           # 路由分发 + VAR_ 变量解析
  tools.csv                   # 工具注册表
  git_ops/                    # 15 个 Git 工具 (采集/动作/生成) + 各工具 LLM prompts/
  linux_ops/                  # Linux 诊断工具
prompts/                      # 节点级 Thinker + Formatter prompts
sop/                          # 7 个 SOP markdown + sops.csv 索引 + draft/ 草稿
user/                         # 用户数据: config/ (模型+运行时配置), sessions/ (会话JSON)
utils/                        # 资源加载、流式输出、日志、SOP加载、TTS
tests/                        # 单元测试 + demo 环境
intro/                        # 项目文档（架构 + 设计 + 环境配置）
history/                      # 会话日志 {ts}_{slug}/
```

## 5. 运行须知

当前是python虚拟环境，运行前记得 source .venv/bin/activate
网络有问题时可走代理7897

