import os
from langchain_ollama import ChatOllama
from utils.streaming import stream_llm

_PROMPT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "prompts", "report_generator")


def _load_system_prompt() -> str:
    path = os.path.join(_PROMPT_DIR, "system.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def generate_summary_report(data: str) -> str:
    """调用LLM对任意文本数据进行分析并生成结构化的总结报告。"""
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        llm = ChatOllama(
            model="qwen3:4b-instruct_q8_8k",
            base_url=base_url,
            temperature=0.2,
            num_predict=4096,
        )

        system_prompt = _load_system_prompt()
        prompt = (
            f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            f"<|im_start|>user\n原始数据：\n{data}\n\n请生成总结报告。<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        print("  [report_generator] ", end="", flush=True)
        report, _ = stream_llm(llm, prompt)
        report = str(report)

        return (
            f"成功 | 已经通过子代理生成了一份详细的总结报告\n"
            f"[DETAIL]\n"
            f"{report}"
        )

    except Exception as e:
        return f"失败 | 生成报告时发生异常: {str(e)}"
