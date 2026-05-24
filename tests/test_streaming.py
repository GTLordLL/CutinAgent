"""
测试 ChatOllama 流式输出是否正常工作。
运行: source .venv/bin/activate && python tests/test_streaming.py

验证项:
1. .stream() 是否逐个 token 返回（非一次性返回全文）
2. token 之间是否有明显延迟
3. 累积的 full_text 是否正确
4. 最后一个 chunk 是否包含 usage_metadata
5. invoke() 对比（一次性返回完整文本，无中间输出）
"""

import sys
import os
import time

# 确保能从项目根目录运行
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from langchain_ollama import ChatOllama
from langchain_core.messages import HumanMessage

BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
MODEL_ID = "qwen3:4b-instruct_q8_8k"

PROMPT = (
    "<|im_start|>system\n用中文简洁回答，不超过30字。<|im_end|>\n"
    "<|im_start|>user\n请问候用户，并说明你能帮助处理Git相关的开发任务。<|im_end|>\n"
    "<|im_start|>assistant\n"
)


def test_streaming():
    """测试 .stream() 流式输出"""
    print("=" * 60)
    print("  测试 1: .stream() 流式输出")
    print("=" * 60)

    llm = ChatOllama(model=MODEL_ID, base_url=BASE_URL, temperature=0.0)
    print(f"模型: {MODEL_ID} | base_url: {BASE_URL} | temperature: 0.0")
    print()

    chunks = []
    full_text = ""
    token_count = 0
    last_usage = None
    t_start = time.time()

    print("--- 流式输出开始 ---")
    for chunk in llm.stream([HumanMessage(content=PROMPT)]):
        chunks.append(chunk)
        token = ""
        if hasattr(chunk, "content") and chunk.content:
            token = chunk.content
        elif isinstance(chunk, str):
            token = chunk

        if token:
            print(token, end="", flush=True)
            full_text += token
            token_count += 1

        # 尝试提取 usage_metadata
        if hasattr(chunk, "usage_metadata") and chunk.usage_metadata:
            last_usage = chunk.usage_metadata

    t_elapsed = time.time() - t_start
    print()
    print("--- 流式输出结束 ---")
    print()

    # 结果报告
    print(f"耗时: {t_elapsed:.2f}s")
    print(f"chunk 数量: {len(chunks)}")
    print(f"token 数量 (粗略): {token_count}")
    print(f"累积文本长度: {len(full_text)} 字符")
    print(f"累积文本: 【{full_text}】")
    print()

    if last_usage:
        print(f"usage_metadata (最后 chunk): {last_usage}")
    else:
        print("WARNING: 没有在 chunk 中找到 usage_metadata")

    # 检查所有 chunk 中是否有 usage_metadata
    usage_chunks = [c for c in chunks if hasattr(c, "usage_metadata") and c.usage_metadata]
    if usage_chunks:
        print(f"含 usage_metadata 的 chunk 数: {len(usage_chunks)}")
        for i, c in enumerate(usage_chunks):
            print(f"  chunk[{i}]: {c.usage_metadata}")
    else:
        print("WARNING: 所有 chunk 均无 usage_metadata")

    return full_text, len(chunks) > 1


def test_invoke_comparison():
    """对比测试 .invoke() 模式"""
    print()
    print("=" * 60)
    print("  测试 2: .invoke() 对比（无流式）")
    print("=" * 60)

    llm = ChatOllama(model=MODEL_ID, base_url=BASE_URL, temperature=0.0)

    t_start = time.time()
    print("(等待 invoke 完成，无中间输出)...")
    response = llm.invoke([HumanMessage(content=PROMPT)])
    t_elapsed = time.time() - t_start

    content = str(response.content)
    print(f"耗时: {t_elapsed:.2f}s")
    print(f"invoke 结果: 【{content}】")
    print(f"文本长度: {len(content)} 字符")

    if hasattr(response, "usage_metadata") and response.usage_metadata:
        print(f"usage_metadata: {response.usage_metadata}")
    else:
        print("WARNING: invoke 响应中无 usage_metadata")


if __name__ == "__main__":
    full_text, is_streaming = test_streaming()

    if not full_text:
        print("\n[FAIL] 流式输出未产生任何文本！")
        sys.exit(1)

    if not is_streaming:
        print("\n[WARN] 只收到单个 chunk — 流式可能未生效（或模型输出极短）")

    test_invoke_comparison()

    print()
    print("=" * 60)
    print("  测试完成")
    print("=" * 60)
    print("结论: 如果上面两段输出都是中文问候+Git能力说明，且流式输出")
    print("是逐字出现的（而非一次性弹出），则流式输出正常工作。")
