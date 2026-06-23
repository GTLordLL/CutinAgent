"""通用 LLM 节点执行包装器。

封装 run_in_executor + _runtime_timer 模式，消除 main.py 中
UserCoordinator / Compactor 的三处重复（~51行）。

同时提供 headless 同步版本 run_llm_node_sync，供 CLI 模式使用。
"""

import asyncio
import time
from utils.cancel_token import is_cancelled
from utils.llm_errors import LLMConnectionError


def fmt_elapsed(seconds: float) -> str:
    """格式化耗时：<60s 用 '12s'，>=60s 用 '1m15s'。"""
    if seconds >= 60:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m{s}s"
    return f"{seconds:.0f}s"


def run_llm_node_sync(label: str, node_fn, state: dict) -> tuple[dict, float]:
    """同步执行 LLM 节点函数 —— headless 模式使用。

    无 asyncio、无定时器动画、无 Rich Console。
    直接调用 node_fn(state)，计录耗时。

    Args:
        label: 节点标签（headless 下仅用于日志标识）
        node_fn: 同步可调用，接收 state dict 返回 state 更新 dict
        state: 当前 state dict

    Returns:
        (result_dict, elapsed_seconds)
    """
    t_start = time.time()
    try:
        result = node_fn(state)
    except LLMConnectionError as e:
        e.add_context(f"[{label}]")
        raise
    elapsed = time.time() - t_start
    return result, elapsed


async def run_llm_node(label: str, node_fn, state: dict,
                       top_status_data: dict, app, console) -> tuple[dict, float]:
    """在线程池中运行同步 LLM 节点函数，后台定时器实时显示耗时。

    Args:
        label: 显示在顶部运行时状态栏的标签（如 "UserCoordinator"）
        node_fn: 同步可调用，接收 state dict 返回 state 更新 dict
        state: 当前 state dict
        top_status_data: mutable dict，runtime_text 字段被定时器更新
        app: prompt_toolkit Application（用于 invalidate）
        console: Rich Console

    Returns:
        (result_dict, elapsed_seconds)
    """
    loop = asyncio.get_running_loop()
    t_start = time.time()
    stop_event = asyncio.Event()

    async def _timer():
        """后台定时器：每 0.1s 刷新顶部状态栏动画（spinner + dots + 颜色 + 计时）。"""
        try:
            while not stop_event.is_set():
                elapsed = time.time() - t_start
                top_status_data["label"] = label
                top_status_data["elapsed"] = elapsed
                app.invalidate()
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=0.1)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass

    timer_task = asyncio.create_task(_timer())

    try:
        result = await loop.run_in_executor(None, node_fn, state)
    except LLMConnectionError as e:
        # 附加节点上下文后重新抛出，让上层统一展示
        e.add_context(f"[{label}]")
        raise
    finally:
        stop_event.set()
        await timer_task
        top_status_data["label"] = ""
        top_status_data["elapsed"] = 0
        app.invalidate()

    elapsed = time.time() - t_start
    if not is_cancelled():
        console.print(f"[dim]{label} 耗时: {fmt_elapsed(elapsed)}[/dim]")

    return result, elapsed
