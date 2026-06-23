import os
from langchain_ollama import ChatOllama
from utils.streaming import stream_llm
from utils.llm_errors import LLMConnectionError
from repl.config_manager import get_config

_PROMPT_DIR = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    "prompts", "pr_description"
)


def _load_system_prompt() -> str:
    path = os.path.join(_PROMPT_DIR, "system.md")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return f.read().strip()
    return ""


def generate_pr_description(diff: str, commits: str) -> dict:
    """调用 LLM 从 git diff + 提交历史生成 PR 标题、描述和测试计划。

    Args:
        diff: git diff 输出文本（必填），通常引用 VAR_get_git_diff。
        commits: 领先提交列表文本（必填），通常引用 VAR_get_git_commits_ahead。
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
        diff_text = diff if len(diff) <= 4000 else diff[:4000] + "\n... (diff 截断)"
        commits_text = commits if len(commits) <= 2000 else commits[:2000] + "\n... (commits 截断)"

        prompt = (
            f"<|im_start|>system\n{system_prompt}<|im_end|>\n"
            f"<|im_start|>user\n"
            f"## Git Diff\n{diff_text}\n\n"
            f"## 提交历史\n{commits_text}\n"
            f"<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        cfg = get_config()
        buf_interval = float(cfg["stream_buffer_interval"])
        if not _headless:
            print("  [generate_pr_description] ", end="", flush=True)
        description, usage = stream_llm(
            llm, prompt, buffer_interval=buf_interval, silent=_headless
        )
        description = description.strip()

        return {
            "status": "成功",
            "summary": "已生成 PR 描述",
            "detail": description,
            "token_usage": usage,
        }

    except LLMConnectionError as e:
        return {"status": "失败", "summary": str(e), "detail": ""}
    except Exception as e:
        return {
            "status": "失败",
            "summary": f"生成 PR 描述时发生异常: {str(e)}",
            "detail": "",
        }
