import os
from langchain_ollama import ChatOllama
from utils.streaming import stream_llm
from repl.config_manager import get_config

_PROMPT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "prompts", "daily_report"
)


def _load_system_prompt() -> str:
    path = os.path.join(_PROMPT_DIR, "system.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def generate_daily_report(data: str) -> dict:
    """调用 LLM 从 git log 生成今日变更日报。"""
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

        llm = ChatOllama(
            model="qwen3:4b-instruct_q8_8k",
            base_url=base_url,
            temperature=0.2,
            num_predict=2048,
        )

        system_prompt = _load_system_prompt()
        prompt = (
            f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            f"<|im_start|>user\nGit 提交记录:\n{data}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        cfg = get_config()
        buf_interval = float(cfg["stream_buffer_interval"])
        print("  [generate_daily_report] ", end="", flush=True)
        report, usage = stream_llm(llm, prompt, buffer_interval=buf_interval)
        report = report.strip()

        return {
            "status": "成功",
            "conclusion": "已生成今日变更日报",
            "summary": report,
            "detail": report,
            "token_usage": usage,
        }

    except Exception as e:
        return {"status": "失败", "conclusion": f"生成日报时发生异常: {str(e)}", "summary": "", "detail": ""}
