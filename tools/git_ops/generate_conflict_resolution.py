import os
from langchain_ollama import ChatOllama
from utils.streaming import stream_llm
from repl.config_manager import get_config

_PROMPT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "prompts", "conflict_resolution"
)


def _load_system_prompt() -> str:
    path = os.path.join(_PROMPT_DIR, "system.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def generate_conflict_resolution(data: str) -> dict:
    """调用 LLM 分析 Git 冲突并给出解决方案建议。

    Args:
        data: get_git_conflicts 输出的冲突文件及冲突标记文本（必填）。
    """
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        _headless = os.environ.get("CUTIN_HEADLESS") == "1"

        llm = ChatOllama(
            model="qwen3:4b-instruct_q8_8k",
            base_url=base_url,
            temperature=0.2,
            num_predict=3072,
        )

        system_prompt = _load_system_prompt()

        # 截断过长的冲突内容，保留足够上下文供分析
        conflict_text = data if len(data) <= 8000 else data[:8000] + "\n... (冲突内容已截断)"

        prompt = (
            f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            f"<|im_start|>user\n"
            f"## Git 冲突信息\n{conflict_text}\n"
            f"<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        cfg = get_config()
        buf_interval = float(cfg["stream_buffer_interval"])
        if not _headless:
            print("  [generate_conflict_resolution] ", end="", flush=True)
        description, usage = stream_llm(
            llm, prompt, buffer_interval=buf_interval, silent=_headless
        )
        description = description.strip()

        return {
            "status": "成功",
            "conclusion": "已生成冲突分析报告与解决方案建议",
            "summary": description if len(description) <= 500 else description[:500] + "...",
            "detail": description,
            "token_usage": usage,
        }

    except Exception as e:
        return {
            "status": "失败",
            "conclusion": f"生成冲突分析报告时发生异常: {str(e)}",
            "summary": "",
            "detail": "",
        }
