# Cutin Agent (千务小切)

**中文** | [English](./README_EN.md)

基于 Python + LangGraph 的 **SOP 驱动型受控 Agent 框架**。将 LLM 的角色从"自主决策者"转变为"标准化作业程序（SOP）的数字执行员"，专为消费级硬件（RTX 3060 6GB）环境下的 **qwen3:4b** 模型设计。

> **核心价值**：低成本（消费级硬件 + 4B 模型可跑）+ 数据完全本地（不上云，数据主权在你自己手里）。


## 架构

CutinAgent 采用 **REPL 外层 + LangGraph 执行内层** 双层架构。REPL 提供交互式命令循环（`/help` `/sops` `/history` `/clear` `/exit`，Tab 补全），UserCoordinator 做意图分类与渐进确认，确认后加载 SOP 进入 LangGraph 执行图。所有 LLM 调用支持 token 级流式输出。

## 核心设计

11 大设计要点详见 [关键设计概述](intro/design/essentials/关键设计概述.md)，各要点独立论述"做了什么、为什么这么做、不这么做会怎样"：

| # | 设计要点 | 核心思路 | 文档 |
|---|---------|---------|------|
| 3.1 | Thinker + Formatter 双阶段 | Thinker(temp 0.4)自由推理 + Formatter(temp 0.0)结构化提取 + Validator 重试兜底 | [ThinkerFormatter设计.md](intro/design/essentials/ThinkerFormatter设计.md) |
| 3.2 | UserCoordinator 人机协作网关 | 五字段输出 + 三级渐进确认 + IS_EXECUTE 代码闸门 | [UserCoordinator设计.md](intro/design/essentials/UserCoordinator设计.md) |
| 3.3 | Compactor 评价与历史压缩 | TaskCompactor(三字段)+ChatCompactor(单字段)双压缩体系 + 代码管理历史生命周期 + 8K 上下文防溢出 | [Compactor设计.md](intro/design/essentials/Compactor设计.md) / [ChatCompactor设计.md](intro/design/essentials/ChatCompactor设计.md) |
| 3.4 | SOP 存储与校验 | Markdown 7 section + 加载时 13 项校验 + CSV 轻量索引 | [SOP体系设计.md](intro/design/essentials/SOP体系设计.md) |
| 3.5 | 工具合约与变量传递 | 四字段统一契约 + 字典路由 + VAR_ 变量传递 | [工具合约设计.md](intro/design/essentials/工具合约设计.md) |
| 3.6 | 进度更新与重试 | 纯代码机械拼接 + 4 种追加模式 + 剥离-重建重试策略 | [进度更新与重试设计.md](intro/design/essentials/进度更新与重试设计.md) |
| 3.7 | 日志系统 | 按 round+node 分目录 + JSON 快照 + 文本日志互补 | [日志系统设计.md](intro/design/essentials/日志系统设计.md) |
| 3.8 | 图结构与路由 | 3 节点硬编码路由 + task_status 字符串比对 + ProgressUpdater 无条件回 Scheduler | [图结构与路由设计.md](intro/design/essentials/图结构与路由设计.md) |
| 3.9 | REPL UI 与流式输出 | Application(full_screen=False) + patch_stdout + buffer_interval 间隔缓冲 + Rich dim 样式分层 | [ui设计文档.md](intro/design/ui设计文档.md) |
| 3.10 | 会话管理系统 | Session JSON 7字段 + CRUD + 选择器(ConditionalContainer) + 自动保存/命名 + SOP ID 列表快照 | [会话管理设计.md](intro/design/essentials/会话管理设计.md) |
| 3.11 | 配置管理系统 | 两层配置 + Copy-on-Activate + 持久化 JSON + `/config` 选择器 UI + 6 个可配置项 | [配置管理设计.md](intro/design/essentials/配置管理设计.md) |

更多文档：
- 架构总览 — **[架构概述](intro/design/architecture/架构概述.md)** | **[架构论述](intro/design/architecture/架构.md)**
- 解决的痛点 — **[痛点.md](intro/design/痛点.md)**
- 任务与领域分类 — **[任务和领域分类.md](intro/design/任务和领域分类.md)**
- 进度更新机制 — **[进度更新器设计手册.md](intro/design/进度更新器设计手册.md)**
- REPL 模块设计 — **[repl设计文档.md](intro/design/repl设计文档.md)**
- SOP 编写规范 — **[sop编写规范.md](intro/design/sop编写规范.md)**

## 快速开始

### 环境要求

| 组件 | 要求 |
|------|------|
| 操作系统 | Ubuntu 24.04 LTS (x86_64) |
| GPU | NVIDIA RTX 3060 6GB（或同等显存） |
| Docker | Docker Engine + Docker Compose v2 |
| NVIDIA 组件 | NVIDIA 驱动 + NVIDIA Container Toolkit |
| Python | 3.10+ |

> 完整从零配置教程见 **[环境配置说明.md](intro/env/环境配置说明.md)**。

### 一键部署

```bash
git clone https://github.com/GTLordLL/CutinAgent.git
cd CutinAgent
bash setup.sh
source .venv/bin/activate
python main.py
```

`setup.sh` 自动完成：环境自检 → 启动 Ollama 容器 → 拉取模型 → 创建定制模型 → 配置 Python 虚拟环境。全程幂等，失败自动清理。

### 运行

启动后进入 REPL 交互界面，直接输入自然语言指令即可：

- `检查一下docker服务的运行状态`
- `我怀疑/var/log目录磁盘占用太大`
- `对当前系统做一次全面的健康检查`

支持 `/help` `/sops` `/history` `/clear` `/exit` 等 REPL 命令，Tab 补全。所有 LLM 推理 token 级流式输出到终端。

## 项目结构

```
cutin_agent/
├── main.py                  # 入口：资源初始化 → REPL 循环编排（调用 repl/ 各模块）
├── pyproject.toml           # pip install -e . 打包定义 + [project.scripts] 入口 cutin
├── repl/                    # REPL 基础设施
│   ├── command_handler.py   # / 命令分发 + Tab 补全 (ReplCompleter)
│   ├── command_hint.py      # 命令提示功能（输入时的命令建议）
│   ├── ui_renderer.py       # Rich 渲染函数 (print_welcome, print_user_message 等)
│   ├── app_builder.py       # prompt_toolkit 组件工厂 (多选择器容器)
│   ├── state_manager.py     # State 创建、重置
│   ├── session_manager.py   # 会话 CRUD (save/load/list/delete)
│   ├── session_picker.py    # 会话选择器 UI (ConditionalContainer)
│   ├── sop_picker.py        # SOP 多选选择器 UI
│   ├── sop_runner.py        # LangGraph SOP 图执行封装 + 节点计时 + Panel 渲染
│   ├── config_manager.py    # 运行时全局配置管理 (get/apply/reset + JSON 持久化)
│   ├── config_picker.py     # 全局设置选择器 UI (Copy-on-Activate)
│   ├── execution_controller.py  # SOP 执行流程控制 (确认→执行→评价→满意度)
│   ├── compaction_controller.py # 自动压缩控制 (token 阈值检查 + ChatCompactor 调用)
│   └── ...
├── graph/                   # LangGraph StateGraph 构建与路由
├── llm_nodes/               # LLM 节点 (Thinker+Formatter 双阶段)
│   ├── UserCoordinatorNode.py   # 人机协作网关（含 SOP 匹配）
│   ├── TaskCompactorNode.py     # SOP 执行评价 + 对话/执行历史压缩
│   ├── ChatCompactorNode.py     # 对话上下文压缩（手动/自动触发）
│   └── SopExecutionSchedulerNode.py  # 步骤调度 + 工具调用决策
├── data_nodes/              # 非 LLM 数据节点
│   ├── ToolExecutor.py      # 工具分发 + 结果四字段处理 + 并行调用
│   ├── ProgressUpdater.py   # 纯代码进度更新（4 种追加模式）
│   └── VariableStore.py     # 内存变量存储 (VAR_xxx)
├── parsers/                 # 纯文本解析 (无副作用，不调 LLM)
├── validator/               # 输出校验 (防幻觉)
├── prompts/                 # 节点级提示词模板 (thinker + formatter)
├── tools/                   # 工具箱：ToolDispatcher + 工具注册表 + 10+ 诊断工具
├── sop/                     # SOP 技能库 (Markdown 文件 + CSV 索引)
├── user/                    # 用户数据（配置持久化 + 会话 JSON）
├── utils/                   # 资源加载、日志、流式输出、TTS 引擎
├── tests/                   # 单元测试
└── intro/                   # 项目文档（环境配置 + 设计文档）
```

## 新增 SOP

新增 SOP 不改框架代码，但需满足前置条件：

1. **理解工具集**：熟悉 `tools/tools.csv` 中每个工具的功能和参数约束
2. **如果工具不够**：按四字段契约格式封装新工具，注册到 `tools/tools.csv`
3. **编写 SOP 文件**：创建 `sop/NEW_SKILL.md`，包含 7 个标准 section
4. **注册索引**：在 `sop/sops.csv` 中添加一行索引

SOP 编写规范详见 [sop编写规范.md](intro/design/sop编写规范.md)。

## 许可证

本项目采用 **GNU Affero General Public License v3 (AGPL-3.0)** 许可证。简言之：

- **自由使用**：你可以自由使用、修改和分发本项目
- **开源传染**：对本项目的任何修改和衍生作品，如果通过网络提供服务，必须同样以 AGPL-3.0 开源
- **商用限制**：如需闭源商用授权，请联系开发者单独协商

详见 [LICENSE](LICENSE) 文件。
