import time
from rich.console import Console
from validator.CompactorValidator import validate_compactor_output
from utils.debug_logger import log_node_io
from utils.streaming import stream_llm
from repl.dialogue_utils import dialogue_to_text
from repl.config_manager import get_config


def task_compactor_node(resources, headless=False):
    """TaskCompactor 可调用对象工厂。

    返回一个函数，接收 state dict，执行 Thinker+Formatter 双阶段推理，
    返回 state 更新 dict。

    不注册为 LangGraph 节点 —— 由 main.py REPL 循环直接调用。

    Args:
        resources: LLMResources 实例
        headless: True 时完全静默，不输出任何内容到终端
    """
    thinker_llm = resources.get_llm("compactor_thinker")
    formatter_llm = resources.get_llm("all_formatter")
    thinker_prompt = resources.prompts["compactor_thinker"]
    formatter_prompt = resources.prompts["compactor_formatter"]
    _console = None if headless else Console()

    def compact_task(state: dict) -> dict:
        cfg = get_config()
        buf_interval = float(cfg["stream_buffer_interval"])
        t_start = time.time()
        round_num = state.get("current_round", 0)

        user_message = state.get("user_instruction", "")
        current_dialogue = state.get("current_dialogue", [])
        conversation_history = state.get("conversation_history", "")
        current_action = state.get("current_action", "")
        long_term_intent = state.get("long_term_intent", "")
        execution_history = state.get("execution_history", "")

        # 构造执行结果摘要
        tool_status = state.get("tool_status", "")
        tool_conclusion = state.get("tool_conclusion", "")
        tool_summary = state.get("tool_summary", "")
        sop_plan_steps = state.get("sop_plan_steps", "")

        latest_execution = (
            f"Status: {tool_status}\n"
            f"Conclusion: {tool_conclusion}\n"
            f"Summary: {tool_summary}\n"
            f"SOP Plan with Progress:\n{sop_plan_steps}"
        )

        # --- Thinker ---
        thinker_input = (
            f"USER_MESSAGE: {user_message}\n\n"
            f"CURRENT_DIALOGUE: {dialogue_to_text(current_dialogue) or 'None'}\n\n"
            f"CONVERSATION_HISTORY: {conversation_history or 'None'}\n\n"
            f"CURRENT_ACTION: {current_action}\n\n"
            f"LONG_TERM_INTENT: {long_term_intent or 'None'}\n\n"
            f"LATEST_EXECUTION_RESULT:\n{latest_execution}\n\n"
            f"EXECUTION_HISTORY: {execution_history or 'None'}\n"
        )
        thinker_raw = (
            f"<|im_start|>system\n{thinker_prompt}<|im_end|>\n"
            f"<|im_start|>user\n{thinker_input}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        if _console:
            _console.out("  [Thinker] ", style="dim")
        reasoning_chain, thinker_tokens = stream_llm(
            thinker_llm, thinker_raw, buffer_interval=buf_interval,
            console=_console, style="dim", silent=headless,
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
                _console.out(f"\n  [Formatter{retry_label}] ", style="dim")
            raw_output, fmt_tokens = stream_llm(
                formatter_llm, current_prompt, buffer_interval=buf_interval,
                console=_console, style="dim", silent=headless,
            )
            if fmt_tokens:
                formatter_tokens_list.append(fmt_tokens)

            is_valid, error_reason, p = validate_compactor_output(raw_output)
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
                "evaluation": "Unable to evaluate the SOP execution due to output parsing failure.",
                "conversation_summary": "User interaction occurred but could not be summarized.",
                "execution_summary": "SOP executed but results could not be compacted.",
            }

        result = {
            "compactor_evaluation": parsed.get("evaluation", ""),
            "compactor_conversation_summary": parsed.get("conversation_summary", ""),
            "compactor_execution_summary": parsed.get("execution_summary", ""),
        }

        log_node_io(
            node_name="TaskCompactor",
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

    return compact_task
