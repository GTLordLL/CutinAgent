"""
LLM 流式输出工具。

提供 stream_llm() 函数，封装 ChatOllama.stream() 调用，
实时输出 token，同时累积完整文本供下游使用。
"""

import sys
import time
from typing import Callable
from langchain_core.messages import HumanMessage
from rich.console import Console


def stream_llm(llm, prompt_text: str, label: str = "",
               live_callback: Callable[[str], None] | None = None,
               buffer_interval: float = 0,
               console: Console | None = None,
               style: str = "") -> tuple[str, dict]:
    """流式调用 LLM，实时或间隔输出 token。

    Args:
        llm: ChatOllama 实例。
        prompt_text: 完整的 prompt 文本（含 <|im_start|> 等标记）。
        label: 输出前缀标签，如 "[Thinker] "。
        live_callback: 可选回调，每收到 token 时调用。用于 Rich Live 渲染。
        buffer_interval: 间隔秒数，>0 时每 N 秒批量 flush 到 stdout（降低 patch_stdout 压力）。
        console: Rich Console 实例，用于带样式的输出。
        style: Rich style 字符串，如 "dim"。

    Returns:
        (full_text, usage_dict): 累积的完整响应文本和 token 用量信息。
    """
    full_text = ""
    usage = {}
    last_flush_pos = 0
    last_flush_time = time.time()

    def _write(text: str):
        """写入 stdout，优先使用 Rich Console 样式输出。"""
        if console and style:
            console.out(text, style=style, end="")
            console.file.flush()
        else:
            sys.stdout.write(text)
            sys.stdout.flush()

    for chunk in llm.stream([HumanMessage(content=prompt_text)]):
        token = ""
        if hasattr(chunk, "content") and chunk.content:
            token = chunk.content

        if token:
            full_text += token

        if not usage and hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
            raw = dict(chunk.usage_metadata)
            usage = {
                "input": raw.get("input_tokens", 0),
                "output": raw.get("output_tokens", 0),
                "total": raw.get("total_tokens", 0),
            }

        if buffer_interval > 0 and not live_callback:
            now = time.time()
            if now - last_flush_time >= buffer_interval:
                new_text = full_text[last_flush_pos:]
                if new_text:
                    _write(new_text)
                last_flush_pos = len(full_text)
                last_flush_time = now
        elif token and not live_callback:
            _write(token)

    if buffer_interval > 0 and not live_callback:
        new_text = full_text[last_flush_pos:]
        if new_text:
            _write(new_text)
    elif not live_callback:
        _write("\n")

    return full_text, usage
