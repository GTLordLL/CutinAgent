# Cutin Agent (千务小切)

[中文](./README.md) | **English**

An **SOP-driven controlled Agent framework** built on Python + LangGraph. It transforms the LLM's role from "autonomous decision-maker" into a "digital executor of Standard Operating Procedures (SOPs)", designed for consumer-grade hardware (RTX 3060 6GB) running the **qwen3:4b** model.

> **Core Value**: Low cost (consumer GPU + 4B model) + fully local data (no cloud — your data stays with you).
>
> **What to Know**: This is not a "chat-and-serve" bot. You write SOPs (standard operating procedures) to tell the Agent what to do — SOP authoring has a learning curve. Use Claude Code or similar large models to help write and debug SOPs.
>
> **In a Nutshell**: Write procedures in Markdown, execute them locally with a 4B model — turning AI Agents from "black-box autonomy" into "white-box process execution."

## Architecture

v2 uses a **REPL outer layer + LangGraph execution inner layer** dual architecture. The REPL provides an interactive command loop (`/help` `/sops` `/history` `/clear` `/exit`, with Tab completion). UserCoordinator handles intent classification and progressive confirmation; once confirmed, the SOP is loaded into the LangGraph execution graph. All LLM calls support token-level streaming output.

## Core Design

8 key design points — see [Design Overview](intro/design/essentials/关键设计概述.md) for the full picture. Each point covered in its own deep-dive document (Chinese only):

| # | Design Point | Core Idea | Document |
|---|-------------|-----------|---------|
| 1 | Thinker + Formatter Dual-Phase | Thinker (temp 0.4) free reasoning + Formatter (temp 0.0) structured extraction + Validator retry | [ThinkerFormatter设计.md](intro/design/essentials/ThinkerFormatter设计.md) |
| 2 | UserCoordinator Gateway | 5-field output + 3-stage progressive confirmation + IS_EXECUTE code gate | [UserCoordinator设计.md](intro/design/essentials/UserCoordinator设计.md) |
| 3 | Compactor History Compression | 3-field output + code-managed history lifecycle + 8K context overflow prevention | [Compactor设计.md](intro/design/essentials/Compactor设计.md) |
| 4 | SOP Storage & Validation | Markdown 7-section + 13-rule load-time validation + CSV lightweight index | [SOP体系设计.md](intro/design/essentials/SOP体系设计.md) |
| 5 | Tool Contract & Variable Passing | 4-field unified contract + dict-based dispatch + VAR_ variable references | [工具合约设计.md](intro/design/essentials/工具合约设计.md) |
| 6 | Progress Update & Retry | Pure-code mechanical concatenation + 4 update modes + strip-rebuild retry strategy | [进度更新与重试设计.md](intro/design/essentials/进度更新与重试设计.md) |
| 7 | Logging System | Per-round per-node directory structure + JSON snapshots + text log complement | [日志系统设计.md](intro/design/essentials/日志系统设计.md) |
| 8 | Graph Structure & Routing | 3-node hardcoded routing + task_status string comparison + ProgressUpdater always returns to Scheduler | [图结构与路由设计.md](intro/design/essentials/图结构与路由设计.md) |

More docs (Chinese):
- Architecture overview — **[Architecture Overview](intro/design/architecture/架构概述.md)** | **[Architecture Deep Dive](intro/design/architecture/架构.md)**
- Pain points solved — **[痛点.md](intro/design/痛点.md)**
- Task & domain classification — **[任务和领域分类.md](intro/design/任务和领域分类.md)**
- Progress update mechanism — **[进度更新器设计手册.md](intro/design/进度更新器设计手册.md)**
- REPL module design — **[repl设计文档.md](intro/design/repl设计文档.md)**
- SOP authoring guide — **[sop编写规范.md](intro/design/sop编写规范.md)**

## Quick Start

### Requirements

| Component | Requirement |
|-----------|-------------|
| OS | Ubuntu 24.04 LTS (x86_64) |
| GPU | NVIDIA RTX 3060 6GB (or equivalent VRAM) |
| Docker | Docker Engine + Docker Compose v2 |
| NVIDIA | NVIDIA Driver + NVIDIA Container Toolkit |
| Python | 3.10+ |

> Full setup guide: **[ENVIRONMENT_SETUP.md](intro/env/ENVIRONMENT_SETUP.md)**.

### One-Click Setup

```bash
git clone https://github.com/GTLordLL/CutinAgent.git
cd CutinAgent
bash setup.sh
source .venv/bin/activate
python main.py
```

`setup.sh` automates: dependency checks → Ollama container startup → model pull → custom model creation → Python virtual environment. Fully idempotent; cleans up on failure.

### Running

Launch into the REPL interface and type natural language instructions:

- `Check the running status of the docker service`
- `I suspect /var/log is taking up too much disk space`
- `Run a comprehensive system health check`

Supports `/help` `/sops` `/history` `/clear` `/exit` REPL commands with Tab completion. All LLM inference is streamed token-by-token to the terminal.

## Project Structure

```
cutin_agent/
├── main.py                  # Entry point: resource init → REPL loop orchestration
├── repl/                    # REPL infrastructure (commands, state, sessions)
├── config/                  # Model configuration (model_config.json)
├── graph/                   # LangGraph StateGraph build & routing
├── llm_nodes/               # LLM nodes (Thinker+Formatter dual-phase pattern)
├── data_nodes/              # Non-LLM data nodes (ToolExecutor, ProgressUpdater)
├── prompts/                 # Prompt templates
├── tools/                   # Toolbox: ToolDispatcher + 11 tools
├── sop/                     # SOP skill library (Markdown files + CSV index)
├── validator/               # Output validation (anti-hallucination)
├── utils/                   # Resource loading, logging, streaming
└── history/                 # Runtime logs (git ignored)
```

## Adding New SOPs

No framework code changes needed, but prerequisites apply:

1. **Know your tools**: familiarize yourself with `tools/tools.csv` — what each tool does and its parameter constraints
2. **If tools are missing**: write a new expert tool following the 4-field contract format, register in `tools/tools.csv`
3. **Write the SOP file**: create `sop/NEW_SKILL.md` with all 7 standard sections
4. **Register the index**: add a row to `sop/sops.csv`

SOP authoring guidelines: [sop编写规范.md](intro/design/sop编写规范.md) (Chinese).

## License

MIT License
