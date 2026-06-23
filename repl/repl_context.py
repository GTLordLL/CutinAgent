"""REPL 主循环共享状态容器。

将原来 run_repl 中通过闭包隐式捕获的 22 个局部变量，
替换为显式 dataclass 字段，供 keybindings/input_handler 等模块访问。

用法:
    ctx = REPLContext(
        resources=..., app_graph=..., ...,
    )
    # app 在 build_application 后赋值
    ctx.app = build_application(layout, kb)
    ctx.input_field = input_field
"""

import asyncio
from dataclasses import dataclass, field
from typing import Any


@dataclass
class REPLContext:
    """REPL 主循环共享状态。

    字段分为 5 组：资源、LLM 节点、运行时状态、UI 组件、控制标志。
    app / input_field / console 在 run_repl 中逐步赋值，其余在构造时传入。
    """

    # ── 资源 ──
    resources: Any = None
    app_graph: Any = None
    session_dir: str = ""

    # ── LLM 节点函数（callable）──
    user_coordinator_fn: Any = None
    compactor_fn: Any = None
    problem_analyzer_fn: Any = None
    sop_summarizer_fn: Any = None
    tool_dispatcher: Any = None

    # ── 运行时状态 ──
    state: dict = field(default_factory=dict)
    valid_tool_ids: set = field(default_factory=set)

    # ── UI 组件（逐步赋值）──
    input_field: Any = None
    app: Any = None
    console: Any = None

    # ── 状态栏数据 ──
    top_status_data: dict = field(default_factory=dict)
    status_data: dict = field(default_factory=dict)

    # ── 选择器状态 ──
    picker_state: dict = field(default_factory=dict)
    sop_picker_state: dict = field(default_factory=dict)
    config_picker_state: dict = field(default_factory=dict)
    command_hint_state: dict = field(default_factory=dict)

    # ── 控制标志 ──
    flags: dict = field(default_factory=lambda: {"processing": False, "waiting_confirm": False})
    confirm_event: asyncio.Event = field(default_factory=asyncio.Event)
    confirm_value: dict = field(default_factory=dict)
