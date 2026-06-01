"""通用 LLM 节点执行包装器。

封装 run_in_executor + _runtime_timer 模式，消除 main.py 中
UserCoordinator / ChatCompactor 的三处重复（~51行）。
"""

import asyncio
import time


def fmt_elapsed(seconds: float) -> str:
    """格式化耗时：<60s 用 '12s'，>=60s 用 '1m15s'。"""
    if seconds >= 60:
        m = int(seconds // 60)
        s = int(seconds % 60)
        return f"{m}m{s}s"
    return f"{seconds:.0f}s"


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
        """后台定时器：每 0.5s 刷新顶部状态栏的实时耗时。"""
        try:
            while not stop_event.is_set():
                elapsed = time.time() - t_start
                top_status_data["runtime_text"] = f"  {label}: {fmt_elapsed(elapsed)}"
                app.invalidate()
                try:
                    await asyncio.wait_for(stop_event.wait(), timeout=0.5)
                except asyncio.TimeoutError:
                    pass
        except asyncio.CancelledError:
            pass

    timer_task = asyncio.create_task(_timer())

    try:
        result = await loop.run_in_executor(None, node_fn, state)
    finally:
        stop_event.set()
        await timer_task
        top_status_data["runtime_text"] = ""
        app.invalidate()

    elapsed = time.time() - t_start
    console.print(f"[dim]{label} 耗时: {fmt_elapsed(elapsed)}[/dim]")

    return result, elapsed
