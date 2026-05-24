# Cutin Agent (千务小切)

**中文** | [English](./README_EN.md)

基于 Python + LangGraph 的 **SOP 驱动型受控 Agent 框架**。将 LLM 的角色从"自主决策者"转变为"标准化作业程序（SOP）的数字执行员"，专为消费级硬件（RTX 3060 6GB）环境下的 **qwen3:4b** 模型设计。

> **核心价值**：低成本（消费级硬件 + 4B 模型可跑）+ 数据完全本地（不上云，数据主权在你自己手里）。
>
> **需要知道**：这不是一个"对话即服务"的聊天机器人。你需要编写 SOP（操作规范）来告诉 Agent 怎么做——SOP 编写有技术门槛，建议用 Claude Code 等大模型辅助编写和调试。
>
> **一句话总结**：用 Markdown 写操作规范，4B 小模型本地执行——把 AI Agent 从"黑盒自主决策"变成"白盒流程执行"。

## 架构

v2 采用 **REPL 外层 + LangGraph 执行内层** 双层架构。REPL 提供交互式命令循环（`/help` `/sops` `/history` `/clear` `/exit`，Tab 补全），UserCoordinator 做意图分类与渐进确认，确认后加载 SOP 进入 LangGraph 执行图。所有 LLM 调用支持 token 级流式输出。

## 核心设计

6 个设计要点，每篇独立论述"做了什么、为什么这么做、不这么做会怎样"：

| 设计要点 | 文档 |
|---------|------|
| **人机协作网关** — 意图分类 + 三级渐进确认 + IS_EXECUTE 代码闸门 | [UserCoordinator设计.md](intro/design/essentials/UserCoordinator设计.md) |
| **SOP 体系** — Markdown 即代码 + DSL 控制流 + 加载时 13 项校验 | [SOP体系设计.md](intro/design/essentials/SOP体系设计.md) |
| **执行引擎** — Scheduler → ToolExecutor → ProgressUpdater 三节点循环 | [执行引擎设计.md](intro/design/essentials/执行引擎设计.md) |
| **工具合约** — 四字段契约 + VariableStore + VAR_ 变量传递 | [工具合约设计.md](intro/design/essentials/工具合约设计.md) |
| **历史压缩** — Compactor 评价 + 对话/执行历史压缩 + 代码管理生命周期 | [Compactor设计.md](intro/design/essentials/Compactor设计.md) |
| **Thinker+Formatter** — 双阶段推理（temp 0.4 + 0.0）+ Validator 防幻觉 | [ThinkerFormatter设计.md](intro/design/essentials/ThinkerFormatter设计.md) |

更多文档：
- 架构总览 — **[核心设计分析.md](intro/design/核心设计分析.md)**
- 解决的痛点 — **[痛点.md](intro/design/痛点.md)**
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

> 完整从零配置教程见 **[环境配置说明.md](intro/环境配置说明.md)**。

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
├── main.py                  # 入口：资源初始化 → REPL 循环编排
├── repl/                    # REPL 基础设施（命令处理、状态管理、会话管理）
├── config/                  # 模型配置 (model_config.json)
├── graph/                   # LangGraph StateGraph 构建与路由
├── llm_nodes/               # LLM 节点 (Thinker+Formatter 双阶段模式)
├── data_nodes/              # 非 LLM 数据节点 (ToolExecutor, ProgressUpdater)
├── prompts/                 # 提示词模板
├── tools/                   # 工具箱：ToolDispatcher + 11 个工具
├── sop/                     # SOP 技能库 (Markdown 文件 + CSV 索引)
├── validator/               # 输出校验 (防幻觉)
├── utils/                   # 资源加载、日志、流式输出
└── history/                 # 运行时日志（git ignored）
```

## 新增 SOP

新增 SOP 不改框架代码，但需满足前置条件：

1. **理解工具集**：熟悉 `tools/tools.csv` 中每个工具的功能和参数约束
2. **如果工具不够**：按四字段契约格式封装新工具，注册到 `tools/tools.csv`
3. **编写 SOP 文件**：创建 `sop/NEW_SKILL.md`，包含 7 个标准 section
4. **注册索引**：在 `sop/sops.csv` 中添加一行索引

SOP 编写规范详见 [sop编写规范.md](intro/design/sop编写规范.md)。

## License

MIT License
