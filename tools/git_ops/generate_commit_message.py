import os
from langchain_ollama import ChatOllama
from utils.streaming import stream_llm
from repl.config_manager import get_config

_PROMPT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "prompts", "commit_message"
)


def _load_system_prompt() -> str:
    path = os.path.join(_PROMPT_DIR, "system.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def generate_commit_message(data: str) -> dict:
    """调用 LLM 从 git diff 生成 conventional commit message。"""
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        _headless = os.environ.get("CUTIN_HEADLESS") == "1"

        llm = ChatOllama(
            model="qwen3:4b-instruct_q8_8k",
            base_url=base_url,
            temperature=0.2,
            num_predict=512,
        )

        system_prompt = _load_system_prompt()
        prompt = (
            f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            f"<|im_start|>user\nGit Diff:\n{data}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        cfg = get_config()
        buf_interval = float(cfg["stream_buffer_interval"])
        if not _headless:
            print("  [generate_commit_message] ", end="", flush=True)
        message, usage = stream_llm(llm, prompt, buffer_interval=buf_interval, silent=_headless)
        message = message.strip()

        return {
            "status": "成功",
            "summary": "已生成 Commit Message",
            "detail": message,
            "token_usage": usage,
        }

    except Exception as e:
        return {"status": "失败", "summary": f"生成 commit message 时发生异常: {str(e)}", "detail": ""}
