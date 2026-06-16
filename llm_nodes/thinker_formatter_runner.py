"""Thinker + Formatter 双阶段推理共享引擎。

将 5 个 LLM 节点（UserCoordinator / TaskCompactor / ChatCompactor /
ProblemAnalyzer / SopExecutionScheduler）中完全相同的流程提取为单一可复用函数：

    Thinker 推理 → Formatter 重试循环 → Validator 兜底 → log_node_io

每个节点的差异仅通过 3 个回调表达：
    build_thinker_input(state) → str
    validate_output(raw_output, **ctx) → (bool, reason, parsed)
    map_result(parsed, thinker_tokens, **ctx) → dict

用法示例：
    from llm_nodes.thinker_formatter_runner import run_thinker_formatter

    def compact_task(state):
        return run_thinker_formatter(
            state=state, resources=resources,
            thinker_llm_key="compactor_thinker",
            formatter_llm_key="all_formatter",
            thinker_prompt_key="compactor_thinker",
            formatter_prompt_key="compactor_formatter",
            node_name="TaskCompactor",
            build_thinker_input=..., validate_output=...,
            map_result=..., fallback_result=...,
            console=_console,
        )
"""

import time
from rich.console import Console
from utils.debug_logger import log_node_io
from utils.streaming import stream_llm
from repl.config_manager import get_config


def run_thinker_formatter(
    *,
    state: dict,
    resources,
    # ── LLM / prompt 资源键 ──
    thinker_llm_key: str,
    formatter_llm_key: str,
    thinker_prompt_key: str,
    formatter_prompt_key: str,
    node_name: str,
    # ── 节点特有回调 ──
    build_thinker_input,          # (state, **ctx) -> str
    validate_output,              # (raw_output: str, **ctx) -> (bool, str, dict)
    map_result,                   # (parsed: dict, thinker_tokens: dict, **ctx) -> dict
    fallback_result: dict,        # 所有重试耗尽时的兜底输出
    # ── 显示配置 ──
    thinker_label: str = "Thinker",
    formatter_label: str = "Formatter",
    console=None,                 # None = 完全静默; 传入 Console() 以输出
    headless: bool = False,
    formatter_buffer_interval: float = None,
    max_retries: int = 3,
    # ── 额外上下文（传递给回调）──
    **ctx,
) -> dict:
    """执行一轮 Thinker → Formatter → Validator 推理。

    Returns:
        map_result 返回的 state 更新 dict
    """
    cfg = get_config()
    buf_interval = float(cfg["stream_buffer_interval"])
    fmt_buf = formatter_buffer_interval if formatter_buffer_interval is not None else buf_interval
    silent = console is None
    t_start = time.time()
    round_num = state.get("current_round", 0)

    # ── 获取 LLM 实例和 prompt ──
    thinker_llm = resources.get_llm(thinker_llm_key)
    formatter_llm = resources.get_llm(formatter_llm_key)
    thinker_prompt = resources.prompts[thinker_prompt_key]
    formatter_prompt = resources.prompts[formatter_prompt_key]

    # ── 节点特有：构建 Thinker 输入 ──
    thinker_input = build_thinker_input(state, **ctx)

    # ── Thinker 推理 ──
    thinker_raw = (
        f"<|im_start|>system\n{thinker_prompt}<|im_end|>\n"
        f"<|im_start|>user\n{thinker_input}<|im_end|>\n"
        f"<|im_start|>assistant\n"
    )

    if console:
        console.out(f"  [{thinker_label}] ", style="dim")
    reasoning_chain, thinker_tokens = stream_llm(
        thinker_llm, thinker_raw, buffer_interval=buf_interval,
        console=console, style="dim", silent=silent,
    )

    # ── Formatter 重试循环 ──
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
        if console:
            console.out(f"\n  [{formatter_label}{retry_label}] ", style="dim")
        raw_output, fmt_tokens = stream_llm(
            formatter_llm, current_prompt, buffer_interval=fmt_buf,
            console=console, style="dim", silent=silent,
        )
        if fmt_tokens:
            formatter_tokens_list.append(fmt_tokens)

        is_valid, error_reason, p = validate_output(raw_output, **ctx)
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

    # ── Fallback ──
    if not parsed:
        parsed = fallback_result

    # ── 节点特有：映射为 state 更新 dict ──
    result = map_result(parsed, thinker_tokens, **ctx)

    # ── 日志 ──
    log_node_io(
        node_name=node_name,
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
