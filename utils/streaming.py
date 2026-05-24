"""
LLM 流式输出工具。

提供 stream_llm() 函数，封装 ChatOllama.stream() 调用，
实时打印 token 到终端，同时累积完整文本供下游使用。
"""

import sys
from langchain_core.messages import HumanMessage


def stream_llm(llm, prompt_text: str, label: str = "") -> tuple[str, dict]:
    """流式调用 LLM，实时打印 token 到终端。

    Args:
        llm: ChatOllama 实例。
        prompt_text: 完整的 prompt 文本（含 <|im_start|> 等标记）。
        label: 输出前缀标签，如 "[Thinker] "。

    Returns:
        (full_text, usage_dict): 累积的完整响应文本和 token 用量信息。
    """
    full_text = ""
    usage = {}

    for chunk in llm.stream([HumanMessage(content=prompt_text)]):
        token = ""
        if hasattr(chunk, "content") and chunk.content:
            token = chunk.content

        if token:
            sys.stdout.write(token)
            sys.stdout.flush()
            full_text += token

        if not usage and hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
            raw = dict(chunk.usage_metadata)
            # Normalize Ollama keys (input_tokens -> input) to match
            # the convention expected by debug_logger and node callers.
            usage = {
                "input": raw.get("input_tokens", 0),
                "output": raw.get("output_tokens", 0),
                "total": raw.get("total_tokens", 0),
            }

    sys.stdout.write("\n")
    sys.stdout.flush()

    return full_text, usage
