import time
from validator.InitialSOPRetrieverValidator import validate_sop_id
from utils.sop_loader import load_sop_markdown
from utils.debug_logger import log_node_io
from utils.streaming import stream_llm


def initial_sop_retriever_node(resources):
    thinker_llm = resources.get_llm("sop_retriever_thinker")
    formatter_llm = resources.get_llm("all_formatter")
    thinker_prompt = resources.prompts["sop_retriever_thinker"]
    formatter_prompt = resources.prompts["sop_retriever_formatter"]
    sops_df = resources.sops_df
    sop_dir = resources.sop_dir

    def node(state: dict) -> dict:
        t_start = time.time()
        round_num = state.get("current_round", 0)
        user_instruction = state["user_instruction"]
        sop_library = state.get("sop_library_text", "")

        valid_tool_ids = set(resources.tools_df["Tool_ID"].tolist())

        # --- Thinker ---
        thinker_input = (
            f"USER_INSTRUCTION: {user_instruction}\n"
            f"SOP_LIBRARY:\n{sop_library}\n"
        )
        thinker_raw = (
            f"<|im_start|>system\n{thinker_prompt}<|im_end|>\n"
            f"<|im_start|>user\n{thinker_input}<|im_end|>\n"
            f"<|im_start|>assistant\n"
        )

        print("  [Retriever Thinker] ", end="", flush=True)
        reasoning_chain, thinker_tokens = stream_llm(thinker_llm, thinker_raw)

        # --- Formatter with retries ---
        valid_sop_ids = set(sops_df["SOP_ID"].tolist())
        max_retries = 3
        retries = 0
        matched_sop_id = ""
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
            print(f"  [Retriever Formatter{retry_label}] ", end="", flush=True)
            raw_output, fmt_tokens = stream_llm(formatter_llm, current_prompt)
            if fmt_tokens:
                formatter_tokens_list.append(fmt_tokens)

            is_valid, error_reason, sop_id = validate_sop_id(raw_output, valid_sop_ids)
            formatter_logs.append({
                "retry": retries,
                "output": raw_output,
                "valid": is_valid,
                "reason": error_reason if not is_valid else ""
            })

            if is_valid:
                matched_sop_id = sop_id
                break

            retries += 1
            current_prompt += (
                f"{raw_output}<|im_end|>\n"
                f"<|im_start|>user\n格式输出错误，原因：{error_reason}<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )

        # --- 从 markdown 文件加载完整 SOP 内容 ---
        if matched_sop_id and matched_sop_id != "NO_MATCHING_SOP":
            sop_md = load_sop_markdown(matched_sop_id, sop_dir, valid_tool_ids)
            sop_objective = sop_md.get("objective", "")
            sop_plan_steps = sop_md.get("plan_steps", "")
            sop_tools_required = sop_md.get("tools_required", "")
            sop_exception_handling = sop_md.get("exception_handling", "")
            raw_retry = sop_md.get("retry_limit", "3")
            sop_retry_limit = int(raw_retry.strip()) if raw_retry.strip().isdigit() else 3
            task_status = "ONGOING"
        elif matched_sop_id == "NO_MATCHING_SOP":
            sop_objective = "No matching SOP found."
            sop_plan_steps = "N/A"
            sop_tools_required = ""
            sop_exception_handling = ""
            sop_retry_limit = 3
            task_status = "NO_MATCHING_SOP"
        else:
            sop_objective = ""
            sop_plan_steps = ""
            sop_tools_required = ""
            sop_exception_handling = ""
            sop_retry_limit = 3
            task_status = "NO_MATCHING_SOP"

        result = {
            "matched_sop_id": matched_sop_id or "",
            "sop_objective": sop_objective,
            "sop_plan_steps": sop_plan_steps,
            "sop_tools_required": sop_tools_required,
            "sop_exception_handling": sop_exception_handling,
            "task_status": task_status,
            "retry_limit": sop_retry_limit,
        }

        log_node_io(
            node_name="InitialSOPRetriever",
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
