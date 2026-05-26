import sys
import time
from parsers.tool_call import _build_tool_signature, _split_parallel_calls
from validator.SopExecutionSchedulerValidator import validate_tool_call, validate_scheduler_output
from utils.debug_logger import log_node_io
from utils.streaming import stream_llm


def _parse_multiple_tool_calls(tool_call_raw: str, valid_tool_ids: set) -> list[dict]:
    """解析 TOOL_CALL 字符串，支持 | 分隔的多个工具调用。
    Returns: [{tool_id, args}, ...]
    """
    calls = []
    for part in _split_parallel_calls(tool_call_raw):
        if not part:
            continue
        is_valid, reason, parsed = validate_tool_call(part, valid_tool_ids)
        if is_valid:
            calls.append(parsed)
    return calls


def sop_execution_scheduler_node(resources):
    thinker_llm = resources.get_llm("sop_execution_scheduler_thinker")
    formatter_llm = resources.get_llm("all_formatter")
    thinker_prompt = resources.prompts["sop_execution_scheduler_thinker"]
    formatter_prompt = resources.prompts["sop_execution_scheduler_formatter"]
    tools_df = resources.tools_df

    def node(state: dict) -> dict:
        t_start = time.time()
        round_num = state.get("current_round", 0)
        user_instruction = state.get("user_instruction", "")
        sop_plan_steps = state.get("sop_plan_steps", "")
        sop_exception_handling = state.get("sop_exception_handling", "")
        sop_tools_required = state.get("sop_tools_required", "")
        last_step = state.get("last_step", "")

        # --- Filter tools by sop_tools_required ---
        if sop_tools_required:
            required_ids = {t.strip() for t in sop_tools_required.split(",")}
            filtered = tools_df[tools_df["Tool_ID"].isin(required_ids)]
        else:
            filtered = tools_df

        valid_tool_ids = set(filtered["Tool_ID"].tolist())
        tools_lines = []
        for _, row in filtered.iterrows():
            tools_lines.append(_build_tool_signature(row))
        tools_text = "\n".join(tools_lines)

        # --- Thinker ---
        thinker_input = (
            f"USER_INSTRUCTION: {user_instruction}\n\n"
            f"SOP_PLAN:\n{sop_plan_steps}\n\n"
            f"EXCEPTION_HANDLING:\n{sop_exception_handling}\n\n"
            f"LAST_STEP: {last_step}\n\n"
            f"AVAILABLE_TOOLS:\n{tools_text}\n"
        )
        thinker_raw = (
            f"<|im_start|>system\n{thinker_prompt}<|im_end|>\n"
            f"<|im_start|>user\n{thinker_input}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        sys.stdout.write("\033[2m")
        sys.stdout.flush()
        print("  [Scheduler Thinker] ", end="", flush=True)
        reasoning_chain, thinker_tokens = stream_llm(thinker_llm, thinker_raw, buffer_interval=2.0)

        # --- Formatter with retries ---
        max_retries = 3
        retries = 0
        tool_id = ""
        tool_args = {}
        tool_call_raw = ""
        tool_calls_list = []
        last_step_out = ""
        task_status = "ONGOING"
        formatter_logs = []
        formatter_tokens_list = []

        formatter_base = (
            f"<|im_start|>system\n{formatter_prompt}<|im_end|>\n"
            f"<|im_start|>user\nTHINKING_PROCESS:\n{reasoning_chain}\n<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )
        current_prompt = formatter_base

        while retries < max_retries:
            retry_label = " (retry)" if retries > 0 else ""
            print(f"  [Scheduler Formatter{retry_label}] ", end="", flush=True)
            raw_output, fmt_tokens = stream_llm(formatter_llm, current_prompt, buffer_interval=2.0)
            if fmt_tokens:
                formatter_tokens_list.append(fmt_tokens)

            is_valid, error_reason, parsed = validate_scheduler_output(raw_output, valid_tool_ids)
            formatter_logs.append({
                "retry": retries,
                "output": raw_output,
                "valid": is_valid,
                "reason": error_reason if not is_valid else ""
            })

            if is_valid:
                last_step_out = parsed["next_step"]
                tool_call_raw = parsed["tool_call"]
                task_status = parsed["task_status"]

                # Parse tool calls for ToolExecutor (skip for terminal states)
                if tool_call_raw != "None" and task_status == "ONGOING":
                    tool_calls_list = _parse_multiple_tool_calls(
                        tool_call_raw, valid_tool_ids
                    )
                    if tool_calls_list:
                        tool_id = tool_calls_list[0]["tool_id"]
                        tool_args = tool_calls_list[0]["args"]
                break

            retries += 1
            current_prompt += (
                f"{raw_output}<|im_end|>\n"
                f"<|im_start|>user\n格式输出错误，原因：{error_reason}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )

        sys.stdout.write("\033[0m\n")
        sys.stdout.flush()

        result = {
            "current_tool_call": tool_id,
            "current_tool_call_raw": tool_call_raw if tool_call_raw else raw_output.strip(),
            "current_tool_args": tool_args,
            "current_tool_calls": tool_calls_list,
            "last_step": last_step_out,
            "task_status": task_status,
        }

        log_node_io(
            node_name="SopExecutionScheduler",
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

    return node
