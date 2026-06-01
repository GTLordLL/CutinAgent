import time
from rich.console import Console
from validator.UserCoordinatorValidator import validate_coordinator_output
from utils.debug_logger import log_node_io
from utils.streaming import stream_llm
from repl.dialogue_utils import dialogue_to_text


def user_coordinator_node(resources):
    """UserCoordinator 可调用对象工厂。

    返回一个函数，接收 state dict，执行 Thinker+Formatter 双阶段推理，
    返回 state 更新 dict。

    输出 5 字段：CHAT_MESSAGE（始终输出）, SOP_ID, CURRENT_ACTION, LONG_TERM_INTENT, IS_EXECUTE。
    IS_EXECUTE 为总闸：false 时渐进式确认，true 时全部确认完毕可执行。
    """
    thinker_llm = resources.get_llm("user_coordinator_thinker")
    formatter_llm = resources.get_llm("all_formatter")
    thinker_prompt = resources.prompts["user_coordinator_thinker"]
    formatter_prompt = resources.prompts["user_coordinator_formatter"]
    sops_df = resources.sops_df
    valid_sop_ids = set(sops_df["SOP_ID"].tolist())
    _console = Console()

    def coordinator(state: dict) -> dict:
        t_start = time.time()
        round_num = state.get("current_round", 0)

        user_message = state.get("user_instruction", "")
        conversation_history = state.get("conversation_history", "")
        current_dialogue = state.get("current_dialogue", [])
        execution_history = state.get("execution_history", "")
        from utils.sop_loader import build_sop_library_from_ids
        sop_ids = state.get("sop_ids", [])
        sop_library = build_sop_library_from_ids(sops_df, sop_ids)

        # --- Thinker ---
        thinker_input = (
            f"USER_MESSAGE: {user_message}\n\n"
            f"CURRENT_DIALOGUE: {dialogue_to_text(current_dialogue) or 'None'}\n\n"
            f"CONVERSATION_HISTORY: {conversation_history or 'None'}\n\n"
            f"EXECUTION_HISTORY: {execution_history or 'None'}\n\n"
            f"SOP_LIBRARY:\n{sop_library}\n"
        )
        thinker_raw = (
            f"<|im_start|>system\n{thinker_prompt}<|im_end|>\n"
            f"<|im_start|>user\n{thinker_input}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        _console.out("  [Thinker] ", style="dim")
        reasoning_chain, thinker_tokens = stream_llm(thinker_llm, thinker_raw, buffer_interval=2.0, console=_console, style="dim")

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
            _console.out(f"\n  [Formatter{retry_label}] ", style="dim")
            raw_output, fmt_tokens = stream_llm(formatter_llm, current_prompt, buffer_interval=2.0, console=_console, style="dim")
            if fmt_tokens:
                formatter_tokens_list.append(fmt_tokens)

            is_valid, error_reason, p = validate_coordinator_output(raw_output, valid_sop_ids)
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
                "chat_message": "抱歉，我暂时无法理解您的需求。能换个方式描述一下吗？",
                "sop_id": "",
                "current_action": "",
                "long_term_intent": "",
                "is_execute": "false",
            }

        result = {
            "chat_message": parsed.get("chat_message", ""),
            "matched_sop_id": parsed.get("sop_id", ""),
            "current_action": parsed.get("current_action", ""),
            "long_term_intent": parsed.get("long_term_intent", ""),
            "is_execute": parsed.get("is_execute", "false"),
            "thinker_input_tokens": thinker_tokens.get("input", 0) if thinker_tokens else 0,
        }

        log_node_io(
            node_name="UserCoordinator",
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

    return coordinator
