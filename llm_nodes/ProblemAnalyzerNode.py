"""Problem Analyzer LLM 节点（v0.2）。

在 UserCoordinator 之前运行，自主调用信息采集类工具收集实时数据，
归纳当前状态，推断用户意图。Thinker (temp 0.4) + Formatter (temp 0.0) 双阶段。

输出四字段：CURRENT_STATE, CONFIDENCE, TOOL_CALL, MY_UNDERSTANDING
"""

import time
from rich.console import Console
from validator.ProblemAnalyzerValidator import validate_analyzer_output
from utils.debug_logger import log_node_io
from utils.streaming import stream_llm
from repl.dialogue_utils import dialogue_to_text
from repl.config_manager import get_config
from parsers.tool_call import _build_tool_signature


def problem_analyzer_node(resources, headless=False):
    """Problem Analyzer 可调用对象工厂。

    返回一个函数，接收 state dict，执行 Thinker+Formatter 双阶段推理，
    返回 state 更新 dict（含 analyzer_* 字段）。

    Args:
        resources: LLMResources 实例
        headless: True 时禁用终端输出（CLI 模式）
    """
    thinker_llm = resources.get_llm("problem_analyzer_thinker")
    formatter_llm = resources.get_llm("all_formatter")
    thinker_prompt = resources.prompts["problem_analyzer_thinker"]
    formatter_prompt = resources.prompts["problem_analyzer_formatter"]
    tools_df = resources.tools_df
    _console = None if headless else Console()

    # 预构建 GATHERED_TOOLS 文本：仅 Tool_Type == "gather" 的工具
    gather_df = tools_df[tools_df["Tool_Type"] == "gather"]
    _gathered_tools_lines = []
    for _, row in gather_df.iterrows():
        _gathered_tools_lines.append(_build_tool_signature(row))
    GATHERED_TOOLS_TEXT = "\n".join(_gathered_tools_lines)

    def analyzer(state: dict) -> dict:
        cfg = get_config()
        buf_interval = float(cfg["stream_buffer_interval"])
        silent = _console is None
        t_start = time.time()
        round_num = state.get("current_round", 0)

        user_message = state.get("user_instruction", "")
        conversation_history = state.get("conversation_history", "")
        current_dialogue = state.get("current_dialogue", [])
        execution_history = state.get("execution_history", "")

        # --- Thinker ---
        thinker_input = (
            f"USER_MESSAGE: {user_message}\n\n"
            f"CURRENT_DIALOGUE: {dialogue_to_text(current_dialogue) or 'None'}\n\n"
            f"CONVERSATION_HISTORY: {conversation_history or 'None'}\n\n"
            f"EXECUTION_HISTORY: {execution_history or 'None'}\n\n"
            f"GATHERED_TOOLS:\n{GATHERED_TOOLS_TEXT}\n"
        )
        thinker_raw = (
            f"<|im_start|>system\n{thinker_prompt}<|im_end|>\n"
            f"<|im_start|>user\n{thinker_input}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        if _console:
            _console.out("  [Analyzer Thinker] ", style="dim")
        reasoning_chain, thinker_tokens = stream_llm(
            thinker_llm, thinker_raw, buffer_interval=buf_interval,
            console=_console, style="dim", silent=silent
        )

        # --- Formatter with retries ---
        max_retries = 3
        retries = 0
        formatter_logs = []
        formatter_tokens_list = []
        parsed = {}

        formatter_base = (
            f"<|im_start|>system\n{formatter_prompt}<|im_end|>\n"
            f"<|im_start|>user\nTHINKING_PROCESS:\n{reasoning_chain}\n<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        current_prompt = formatter_base

        while retries < max_retries:
            retry_label = " (retry)" if retries > 0 else ""
            if _console:
                _console.out(f"\n  [Analyzer Formatter{retry_label}] ", style="dim")
            raw_output, fmt_tokens = stream_llm(
                formatter_llm, current_prompt, buffer_interval=2.0,
                console=_console, style="dim", silent=silent
            )
            if fmt_tokens:
                formatter_tokens_list.append(fmt_tokens)

            is_valid, error_reason, p = validate_analyzer_output(raw_output)
            formatter_logs.append({
                "retry": retries,
                "output": raw_output,
                "valid": is_valid,
                "reason": error_reason if not is_valid else ""
            })

            if is_valid:
                parsed = p
                break

            retries += 1
            current_prompt += (
                f"{raw_output}<|im_end|>\n"
                f"<|im_start|>user\n格式输出错误，原因：{error_reason}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )

        # --- Fallback if all retries exhausted ---
        if not parsed:
            parsed = {
                "current_state": "无法解析用户意图，需人工确认。",
                "confidence": "low",
                "tool_call": "",
                "my_understanding": "",
            }

        result = {
            "analyzer_current_state": parsed.get("current_state", ""),
            "analyzer_confidence": parsed.get("confidence", "low"),
            "analyzer_tool_call": parsed.get("tool_call", ""),
            "analyzer_my_understanding": parsed.get("my_understanding", ""),
            "thinker_input_tokens": thinker_tokens.get("input", 0) if thinker_tokens else 0,
        }

        log_node_io(
            node_name="ProblemAnalyzer",
            round_num=round_num,
            thinker_input=thinker_input,
            reasoning_chain=reasoning_chain,
            formatter_logs=formatter_logs,
            final_result=result,
            session_dir=state.get("session_dir", ""),
            elapsed_seconds=time.time() - t_start,
            token_usage={"thinker": thinker_tokens, "formatter": formatter_tokens_list},
        )

        return result

    return analyzer
