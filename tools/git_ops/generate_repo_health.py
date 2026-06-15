import os
from langchain_ollama import ChatOllama
from utils.streaming import stream_llm
from repl.config_manager import get_config

_PROMPT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "prompts", "repo_health"
)


def _load_system_prompt() -> str:
    path = os.path.join(_PROMPT_DIR, "system.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def generate_repo_health(status: str, branches: str, log: str) -> dict:
    """调用 LLM 从工作区状态、分支列表、提交历史生成仓库健康报告。

    Args:
        status: git status 输出文本（必填），通常引用 VAR_get_git_status。
        branches: 分支列表文本（必填），通常引用 VAR_get_git_branches。
        log: 近期提交日志文本（必填），通常引用 VAR_get_git_log。
    """
    try:
        base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        _headless = os.environ.get("CUTIN_HEADLESS") == "1"

        llm = ChatOllama(
            model="qwen3:4b-instruct_q8_8k",
            base_url=base_url,
            temperature=0.2,
            num_predict=2048,
        )

        system_prompt = _load_system_prompt()

        # 截断过长的输入，保留足够上下文
        status_text = status if len(status) <= 2000 else status[:2000] + "\n... (status 截断)"
        branches_text = branches if len(branches) <= 3000 else branches[:3000] + "\n... (branches 截断)"
        log_text = log if len(log) <= 3000 else log[:3000] + "\n... (log 截断)"

        prompt = (
            f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            f"<|im_start|>user\n"
            f"## 工作区状态\n{status_text}\n\n"
            f"## 分支列表\n{branches_text}\n\n"
            f"## 近期提交记录（近7天）\n{log_text}\n"
            f"<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        cfg = get_config()
        buf_interval = float(cfg["stream_buffer_interval"])
        if not _headless:
            print("  [generate_repo_health] ", end="", flush=True)
        description, usage = stream_llm(
            llm, prompt, buffer_interval=buf_interval, silent=_headless
        )
        description = description.strip()

        return {
            "status": "成功",
            "conclusion": "已生成仓库健康报告",
            "summary": description,
            "detail": description,
            "token_usage": usage,
        }

    except Exception as e:
        return {
            "status": "失败",
            "conclusion": f"生成仓库健康报告时发生异常: {str(e)}",
            "summary": "",
            "detail": "",
        }
