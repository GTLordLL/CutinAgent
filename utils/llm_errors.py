"""LLM 连接相关异常定义。

提供统一的 LLMConnectionError，用于在 Ollama 无法连接等场景下，
向用户展示友好提示而非大段 traceback。
"""

import urllib.request
import urllib.error

# 尝试导入 httpx 以捕获其连接异常（httpx 是 ollama 的传递依赖）
try:
    import httpx
    _HTTPX_CONNECT_ERRORS = (httpx.ConnectError, httpx.RemoteProtocolError, httpx.TimeoutException)
except ImportError:
    _HTTPX_CONNECT_ERRORS = ()

# Python 内置 ConnectionError + OSError 覆盖大部分网络/连接失败场景
_BUILTIN_CONNECTION_ERRORS = (ConnectionError, OSError)

# 所有可识别的连接异常类型
CONNECTION_EXCEPTIONS = _BUILTIN_CONNECTION_ERRORS + _HTTPX_CONNECT_ERRORS


class LLMConnectionError(Exception):
    """LLM 连接失败异常 —— 携带用户友好的中文提示。

    调用方可据此区分"可恢复的连接问题"与"其他运行时错误"，
    从而避免向用户展示大段 traceback。
    """

    def __init__(self, detail: str = "", base_url: str = ""):
        self.base_url = base_url
        self.detail = detail
        super().__init__(self._build_message(detail, base_url))

    @staticmethod
    def _build_message(detail: str, base_url: str) -> str:
        parts = ["无法连接大模型服务"]
        if base_url:
            parts.append(f"（地址: {base_url}）")
        if detail:
            parts.append(f"\n原因: {detail}")
        parts.append("\n请检查 Ollama 是否已启动并正常运行。")
        return "".join(parts)

    def add_context(self, context: str) -> None:
        """在 detail 前面追加节点/阶段上下文，并重建消息。

        调用方可通过此方法标记异常发生在哪个 LLM 节点，
        如 "[UserCoordinator] "，最终显示为 "原因: [UserCoordinator] Connection refused"。
        """
        if context:
            self.detail = f"{context} {self.detail}"
            self.args = (self._build_message(self.detail, self.base_url),)


def check_ollama_connectivity(base_url: str = "", timeout: float = 3.0) -> tuple[bool, str]:
    """检测 Ollama 服务是否可达。

    向 {base_url}/api/tags 发送 GET 请求（Ollama 标准 API），
    如果响应 200 则认为连通正常。

    Args:
        base_url: Ollama 服务地址，默认从环境变量 OLLAMA_BASE_URL 读取。
        timeout: 请求超时秒数，默认 3 秒。

    Returns:
        (is_connected: bool, message: str)
        - (True, "OK") — 连通正常
        - (False, reason) — 无法连接，reason 为用户友好提示
    """
    import os as _os

    if not base_url:
        base_url = _os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    url = base_url.rstrip("/") + "/api/tags"

    try:
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            if resp.status == 200:
                return True, "OK"
            return False, f"Ollama 返回异常状态码: {resp.status}"
    except urllib.error.URLError as e:
        reason = str(e.reason) if hasattr(e, "reason") else str(e)
        return False, f"无法连接 Ollama（{base_url}）: {reason}"
    except Exception as e:
        return False, f"无法连接 Ollama（{base_url}）: {e}"
