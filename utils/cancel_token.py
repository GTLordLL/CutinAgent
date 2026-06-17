"""协作式取消令牌。

提供线程安全的取消机制：通过在 LLM streaming / graph 迭代 /
Thinker-Formatter 切换等阻塞点调用 check_cancel()，实现用户发起的
任务取消。

用法:
    # 任意线程触发取消
    request_cancel()

    # 阻塞点检查（取消时 raise CancellationError）
    check_cancel()

    # 非抛出检查（条件判断用）
    if is_cancelled():
        ...

    # 重置（新任务开始前）
    reset_cancel()
"""

import threading

_cancel_event = threading.Event()


class CancellationError(Exception):
    """任务被用户取消时抛出的异常。"""
    pass


def is_cancelled() -> bool:
    """检查是否已请求取消（不抛出异常）。"""
    return _cancel_event.is_set()


def check_cancel():
    """如果已请求取消则抛出 CancellationError。

    在阻塞链的关键位置调用，优雅展开调用栈。
    """
    if _cancel_event.is_set():
        raise CancellationError("Task cancelled by user")


def request_cancel():
    """触发取消（可从任意线程安全调用）。"""
    _cancel_event.set()


def reset_cancel():
    """清除取消标志（新任务开始前调用）。"""
    _cancel_event.clear()
