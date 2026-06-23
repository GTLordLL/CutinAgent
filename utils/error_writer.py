"""错误日志写入工具。

将异常详情（traceback + 上下文）写入项目根目录 error/ 下的时间戳文件，
终端只向用户展示文件路径，避免大段 traceback 污染界面。
"""

import os
import traceback
from datetime import datetime

# 项目根目录：utils/ 的父目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ERROR_DIR = os.path.join(_PROJECT_ROOT, "error")


def _ensure_error_dir() -> str:
    """确保 error/ 目录存在，返回其路径。"""
    os.makedirs(_ERROR_DIR, exist_ok=True)
    return _ERROR_DIR


def write_error(exc: Exception, context: str = "") -> str:
    """将异常详情写入时间戳文件，返回文件路径。

    文件内容包含：时间戳、异常类型、异常消息、上下文说明、完整 traceback。

    Args:
        exc: 要记录的异常对象。
        context: 可选的上下文说明（如 "UserCoordinator Thinker 阶段"）。

    Returns:
        error 文件的绝对路径，供终端展示给用户。
    """
    _ensure_error_dir()
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    filename = f"error_{timestamp}.txt"
    filepath = os.path.join(_ERROR_DIR, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"异常类型: {type(exc).__module__}.{type(exc).__qualname__}\n")
        f.write(f"异常消息: {exc}\n")
        if context:
            f.write(f"上下文: {context}\n")
        f.write("\n--- Traceback ---\n")
        # 获取原始异常的 traceback（含 __cause__ 链）
        tb_lines = traceback.format_exception(type(exc), exc, exc.__traceback__)
        f.writelines(tb_lines)

    return filepath
