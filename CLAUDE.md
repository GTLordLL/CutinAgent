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
main.py                       # 入口：资源初始化 → REPL 循环编排（调用 repl/ 各模块）
pyproject.toml                # pip install -e . 打包定义 + [project.scripts] 入口 cutin
repl/                         # REPL 基础设施
  __init__.py                 # 导出所有公开 API
  command_handler.py          # / 命令分发 + Tab 补全 (ReplCompleter)
  command_hint.py             # 命令提示功能（输入时的命令建议）
  ui_renderer.py              # Rich 渲染函数 (print_welcome, print_user_message 等)
  app_builder.py              # prompt_toolkit 组件工厂 (create_input_field, build_application, 多选择器容器 等)
  state_manager.py            # State 创建、重置
  session_manager.py          # 会话 CRUD (save/load/list/delete) + RUN_SUMMARY
  session_controller.py       # 会话生命周期控制 (新建/加载/恢复)
  session_picker.py           # 会话选择器 UI (ConditionalContainer, 8行/5条)
  sop_picker.py               # SOP 多选选择器 UI（多选勾选，Enter确认）
  sop_runner.py               # LangGraph SOP 图执行封装 + 节点计时 + Panel 渲染
  config_manager.py           # 运行时全局配置管理 (get/apply/reset + JSON 持久化)
  config_picker.py            # 全局设置选择器 UI (Copy-on-Activate, 11行)
  compaction_controller.py    # 自动压缩控制 (token 阈值检查 + ChatCompactor 调用)
  execution_controller.py     # SOP 执行流程控制 (确认→执行→评价→满意度)
  dialogue_utils.py           # 对话解析工具 (str↔list[dict] 格式转换)
  keybindings.py              # 全局按键绑定（含三种 Picker 的 filter 隔离）
  llm_runner.py               # LLM 节点统一调用封装（线程池 + 计时 + 状态栏更新）
graph/
  Builder.py                  # StateGraph: 3节点 + 1条件路由（不含 UserCoordinator/Compactor）
  OverallState.py             # 全局状态 TypedDict（含 REPL 状态字段）
  __init__.py
llm_nodes/                    # LLM 节点 (Thinker+Formatter)
  UserCoordinatorNode.py      # REPL 外层：人机协作网关（含 SOP 匹配）
  TaskCompactorNode.py        # REPL 外层：SOP 执行评价 + 对话/执行历史压缩（三字段）
  ChatCompactorNode.py        # REPL 外层：对话上下文压缩（单字段，手动/自动触发）
  SopExecutionSchedulerNode.py # 图内层：步骤调度 + 工具调用决策
  InitialSOPRetrieverNode.py  # [v1 遗留] 不再使用
data_nodes/                   # 非LLM 节点
  ToolExecutor.py             # 工具分发 + 结果四字段处理 + 并行调用
  ProgressUpdater.py          # 纯代码进度更新（4 种追加模式 + 跳过间隙）
  VariableStore.py            # 内存变量存储 (VAR_xxx)
parsers/                      # 纯文本解析 (无副作用)
  __init__.py
  sop_plan.py                 # StepType 枚举, 步骤解析/分类/重构
  tool_call.py                # 工具签名构建, 并行调用分割
validator/
  SopSpecChecker.py           # Plan_Steps DSL 13项校验 + Retry_Limit 校验
  SopExecutionSchedulerValidator.py  # Formatter 输出校验 (单工具+调度器三元组)
  UserCoordinatorValidator.py # 五字段校验 + IS_EXECUTE 闸门规则 + SOP_ID 白名单
  CompactorValidator.py       # 三字段校验
  InitialSOPRetrieverValidator.py    # [v1 遗留] 不再使用
tools/
  __init__.py
  ToolDispatcher.py           # 工具路由分发 + VAR_ 变量解析
  tools.csv                   # 工具注册表 (Tool_ID, Keywords, Func_Desc, Args_Schema, param_desc)
  report_generator.py         # LLM 报告生成器
  linux_ops/                  # 10 个 Linux 诊断工具
  git_ops/                    # Git 操作工具（6 个）
    prompts/                  # 工具 LLM prompts
  prompts/                    # 工具级 LLM prompts
prompts/                      # 节点级 prompts (thinker + formatter)
sop/                          # SOP 存储
  sops.csv                    # SOP 索引 (SOP_ID, Objective, Description, Keywords)
  GIT_SMART_COMMIT.md         # SOP markdown 全文
  GIT_DAILY_SUMMARY.md
  draft/                      # SOP 草稿
user/                         # 用户数据（配置 + 会话持久化）
  config/
    model_config.json         # 各节点 LLM 参数 (model_id, temperature, top_p, etc.)
    load_model_config.py      # 配置加载 + Ollama URL 解析
    user_config.json          # 运行时配置持久化（自动保存/加载）
  sessions/                   # 会话 JSON 文件 ({session_id}.json)
utils/                        # 工具函数
  LLMResources.py             # 资源初始化：LLM 实例 + prompts + CSV 加载
  debug_logger.py             # 节点级调试日志（Thinker 输入/推理链/Formatter 重试/耗时/token）
  streaming.py                # token 级流式输出
  sop_loader.py               # SOP markdown 加载 + SOP_LIBRARY 索引构建
  load_prompts.py             # Prompt 文件加载
  load_csv.py                 # CSV 文件加载
  monitor_token.py            # Token 用量监控
  tts_engine.py               # TTS 语音播报引擎（edge-tts + ffplay + 播报队列）
tests/                        # 单元测试
  __init__.py
  test_retry_logic.py         # ProgressUpdater 重试逻辑
  test_git_smart_commit.py    # GIT_SMART_COMMIT SOP 集成测试
  test_streaming.py           # 流式输出测试
intro/                        # 项目文档（环境配置 + 设计文档）
history/                      # 会话日志 {ts}_{slug}/
```

## 5. 运行须知

当前是python虚拟环境，运行前记得 source .venv/bin/activate
网络有问题时可走代理7897

