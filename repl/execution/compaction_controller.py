"""ChatCompactor 调用封装。

消除 /compact 手动触发和 token>4096 自动触发两处重复（~35行×2）。
"""

from rich.panel import Panel
from repl.execution.llm_runner import run_llm_node
from repl.state.config_manager import get_config


async def run_chat_compactor(chat_compactor_fn, state: dict,
                             top_status_data: dict, app, console,
                             triggered_by: str = "auto") -> bool:
    """运行 ChatCompactor，将摘要追加到 conversation_history 并清空 current_dialogue。

    Args:
        chat_compactor_fn: ChatCompactor 闭包函数
        state: 全局 state dict（原地更新）
        top_status_data: 顶部运行时状态 mutable dict
        app: prompt_toolkit Application
        console: Rich Console
        triggered_by: "manual"（/compact 命令）或 "auto"（token 阈值）

    Returns:
        True 表示执行了压缩并产生了摘要，False 表示无对话可压缩
    """
    if len(state.get("current_dialogue", [])) == 0:
        return False

    if triggered_by == "auto":
        tokens = state.get("thinker_input_tokens", 0)
        console.print(f"[dim][ChatCompactor] 上下文过长({tokens} tokens)，自动压缩...[/dim]")
    else:
        console.print("[dim][ChatCompactor] 压缩对话上下文...[/dim]")

    result, _elapsed = await run_llm_node(
        "ChatCompactor", chat_compactor_fn, state,
        top_status_data, app, console
    )

    state.update(result)
    summary = state.get("chat_conversation_summary", "")

    if summary:
        state["conversation_history"] += "\n" + summary
        state["current_dialogue"] = []
        if triggered_by == "manual":
            console.print(Panel(
                summary,
                title="对话压缩结果", title_align="left", padding=(0, 1),
            ))
        return True
    else:
        if triggered_by == "manual":
            console.print("[dim]对话压缩完成（无新摘要）。[/dim]")
        return False


async def try_auto_compact(state: dict, chat_compactor_fn,
                           top_status_data: dict, app, console) -> bool:
    """判断 token > 4096 则自动压缩。

    Returns:
        True 表示执行了自动压缩，False 表示无需压缩
    """
    cfg = get_config()
    if (state.get("thinker_input_tokens", 0) > cfg["auto_compact_threshold"]
            and len(state.get("current_dialogue", [])) > 0):
        return await run_chat_compactor(
            chat_compactor_fn, state, top_status_data, app, console,
            triggered_by="auto"
        )
    return False
