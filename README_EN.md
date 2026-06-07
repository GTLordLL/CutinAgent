# Cutin Agent (千务小切)

[中文](./README.md) | **English**

An **SOP-driven controlled Agent framework** built on Python + LangGraph. It transforms the LLM's role from "autonomous decision-maker" into a "digital executor of Standard Operating Procedures (SOPs)", designed for consumer-grade hardware (RTX 3060 6GB) running the **qwen3:4b** model.

> **Core Value**: Low cost (consumer GPU + 4B model) + fully local data (no cloud — your data stays with you).
>
> **What to Know**: This is not a "chat-and-serve" bot. You write SOPs (standard operating procedures) to tell the Agent what to do — SOP authoring has a learning curve. Use Claude Code or similar large models to help write and debug SOPs.
>
> **In a Nutshell**: Write procedures in Markdown, execute them locally with a 4B model — turning AI Agents from "black-box autonomy" into "white-box process execution."

## Architecture

CutinAgent uses a **REPL outer layer + LangGraph execution inner layer** dual architecture. The REPL provides an interactive command loop (`/help` `/sops` `/history` `/clear` `/exit`, with Tab completion). UserCoordinator handles intent classification and progressive confirmation; once confirmed, the SOP is loaded into the LangGraph execution graph. All LLM calls support token-level streaming output.

## Core Design

11 key design points — see [Design Overview](intro/design/essentials/关键设计概述.md) for the full picture. Each point covered in its own deep-dive document (Chinese only):

| # | Design Point | Core Idea | Document |
|---|-------------|-----------|---------|
| 3.1 | Thinker + Formatter Dual-Phase | Thinker (temp 0.4) free reasoning + Formatter (temp 0.0) structured extraction + Validator retry | [ThinkerFormatter设计.md](intro/design/essentials/ThinkerFormatter设计.md) |
| 3.2 | UserCoordinator Gateway | 5-field output + 3-stage progressive confirmation + IS_EXECUTE code gate | [UserCoordinator设计.md](intro/design/essentials/UserCoordinator设计.md) |
| 3.3 | Compactor History Compression | TaskCompactor (3-field) + ChatCompactor (1-field) dual compression + code-managed history lifecycle + 8K context overflow prevention | [Compactor设计.md](intro/design/essentials/Compactor设计.md) / [ChatCompactor设计.md](intro/design/essentials/ChatCompactor设计.md) |
| 3.4 | SOP Storage & Validation | Markdown 7-section + 13-rule load-time validation + CSV lightweight index | [SOP体系设计.md](intro/design/essentials/SOP体系设计.md) |
| 3.5 | Tool Contract & Variable Passing | 4-field unified contract + dict-based dispatch + VAR_ variable references | [工具合约设计.md](intro/design/essentials/工具合约设计.md) |
| 3.6 | Progress Update & Retry | Pure-code mechanical concatenation + 4 update modes + strip-rebuild retry strategy | [进度更新与重试设计.md](intro/design/essentials/进度更新与重试设计.md) |
| 3.7 | Logging System | Per-round per-node directory structure + JSON snapshots + text log complement | [日志系统设计.md](intro/design/essentials/日志系统设计.md) |
| 3.8 | Graph Structure & Routing | 3-node hardcoded routing + task_status string comparison + ProgressUpdater always returns to Scheduler | [图结构与路由设计.md](intro/design/essentials/图结构与路由设计.md) |
| 3.9 | REPL UI & Streaming Output | Application(full_screen=False) + patch_stdout + buffer_interval spacing + Rich dim style layering | [ui设计文档.md](intro/design/ui设计文档.md) |
| 3.10 | Session Management | Session JSON 7-field + CRUD + picker (ConditionalContainer) + auto-save/naming + SOP ID list snapshot | [会话管理设计.md](intro/design/essentials/会话管理设计.md) |
| 3.11 | Configuration Management | Two-layer config + Copy-on-Activate + JSON persistence + `/config` picker UI + 6 configurable items | [配置管理设计.md](intro/design/essentials/配置管理设计.md) |

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
├── main.py                  # Entry: resource init → REPL loop orchestration
├── pyproject.toml           # pip install -e . package definition + [project.scripts] entry
├── repl/                    # REPL infrastructure
│   ├── command_handler.py   # / command dispatch + Tab completion (ReplCompleter)
│   ├── command_hint.py      # Command hint (inline suggestions while typing)
│   ├── ui_renderer.py       # Rich render functions (print_welcome, print_user_message, etc.)
│   ├── app_builder.py       # prompt_toolkit component factory (multi-picker containers)
│   ├── state_manager.py     # State creation & reset
│   ├── session_manager.py   # Session CRUD (save/load/list/delete)
│   ├── session_picker.py    # Session picker UI (ConditionalContainer)
│   ├── sop_picker.py        # SOP multi-select picker UI
│   ├── sop_runner.py        # LangGraph SOP graph execution + node timing + Panel render
│   ├── config_manager.py    # Runtime global config (get/apply/reset + JSON persistence)
│   ├── config_picker.py     # Settings picker UI (Copy-on-Activate)
│   ├── execution_controller.py  # SOP execution flow (confirm → run → evaluate → satisfaction)
│   ├── compaction_controller.py # Auto-compaction (token threshold + ChatCompactor)
│   └── ...
├── graph/                   # LangGraph StateGraph build & routing
├── llm_nodes/               # LLM nodes (Thinker+Formatter dual-phase)
│   ├── UserCoordinatorNode.py   # Human-AI collaboration gateway (incl. SOP matching)
│   ├── TaskCompactorNode.py     # SOP execution evaluation + dialogue/execution compression
│   ├── ChatCompactorNode.py     # Dialogue context compression (manual/auto trigger)
│   └── SopExecutionSchedulerNode.py  # Step scheduling + tool call decisions
├── data_nodes/              # Non-LLM data nodes
│   ├── ToolExecutor.py      # Tool dispatch + 4-field result handling + parallel calls
│   ├── ProgressUpdater.py   # Pure-code progress update (4 append modes)
│   └── VariableStore.py     # In-memory variable store (VAR_xxx)
├── parsers/                 # Pure text parsing (no side effects, no LLM)
├── validator/               # Output validation (anti-hallucination)
├── prompts/                 # Node-level prompt templates (thinker + formatter)
├── tools/                   # Toolbox: ToolDispatcher + tool registry + 10+ diagnostic tools
├── sop/                     # SOP skill library (Markdown files + CSV index)
├── user/                    # User data (config persistence + session JSON)
├── utils/                   # Resource loading, logging, streaming, TTS engine
├── tests/                   # Unit tests
└── intro/                   # Documentation (env setup + design docs)
```

## Adding New SOPs

No framework code changes needed, but prerequisites apply:

1. **Know your tools**: familiarize yourself with `tools/tools.csv` — what each tool does and its parameter constraints
2. **If tools are missing**: write a new expert tool following the 4-field contract format, register in `tools/tools.csv`
3. **Write the SOP file**: create `sop/NEW_SKILL.md` with all 7 standard sections
4. **Register the index**: add a row to `sop/sops.csv`

SOP authoring guidelines: [sop编写规范.md](intro/design/sop编写规范.md) (Chinese).

## License

This project is licensed under the **GNU Affero General Public License v3 (AGPL-3.0)**. In short:

- **Free Use**: You are free to use, modify, and distribute this project
- **Copyleft**: Any modifications or derivative works that are served over a network must also be open-sourced under AGPL-3.0
- **Commercial Restriction**: For closed-source commercial licensing, please contact the developer separately

See [LICENSE](LICENSE) for the full text.
