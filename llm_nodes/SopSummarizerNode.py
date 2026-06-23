"""SopSummarizer 单阶段 LLM 节点。

在 SOP 执行完成后运行，读取 USER_INSTRUCTION + SOP_PLAN_WITH_RESULTS（sop_plan_steps），
输出 1-3 句中文总结（纯文本，≤500 字符）。

单阶段设计：直接调用 stream_llm()，不走 Thinker+Formatter 双阶段。
原因：输出是纯文本无格式歧义，无需 Formatter 提取字段。
"""

from rich.console import Console
from utils.streaming import stream_llm
from validator.SopSummarizerValidator import validate_sop_summary


def sop_summarizer_node(resources, headless=False):
    """SopSummarizer 可调用对象工厂。

    Args:
        resources: LLMResources 实例
        headless: True 时完全静默，不输出任何内容到终端
    """
    _console = None if headless else Console()
    _llm = resources.get_llm("sop_summarizer")
    _prompt = resources.prompts["sop_summarizer"]

    def summarize(state: dict) -> dict:
        user_instruction = state.get("user_instruction", "")
        sop_plan_steps = state.get("sop_plan_steps", "")

        # 截断 sop_plan_steps 到末尾 4000 字符
        truncated_steps = sop_plan_steps
        if len(sop_plan_steps) > 4000:
            truncated_steps = "..." + sop_plan_steps[-4000:]

        # 构建 <|im_start|> 格式 prompt
        user_input = (
            f"USER_INSTRUCTION: {user_instruction}\n\n"
            f"SOP_PLAN_WITH_RESULTS: {truncated_steps or 'None'}"
        )
        prompt_text = (
            f"<|im_start|>system\n{_prompt}<|im_end|>\n"
            f"<|im_start|>user\n{user_input}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        # 单阶段 LLM 调用
        raw_output, _usage = stream_llm(
            _llm, prompt_text,
            label="SopSummarizer",
            console=_console,
            style="dim",
            silent=headless,
        )

        # 校验
        is_valid, _reason, parsed = validate_sop_summary(raw_output)
        if is_valid:
            summary_text = parsed.get("summary", "")
        else:
            # Fallback: 取前 500 字符
            summary_text = raw_output.strip()[:500]

        return {"sop_summary": summary_text}

    return summarize
