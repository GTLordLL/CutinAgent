"""UserCoordinator LLM 节点。

人机协作网关：意图分类 → SOP 匹配 → 参数推导 → TOOL_CALL 输出。
Thinker (temp 0.4) + Formatter (temp 0.0) 双阶段。

输出二字段：CHAT_MESSAGE, TOOL_CALL（Python 函数调用语法或 NONE）。
TOOL_CALL 非 NONE 即表示已匹配 SOP 并填好参数，可进入外部确认。
"""

from rich.console import Console
from repl.dialogue_utils import dialogue_to_text
from llm_nodes.thinker_formatter_runner import run_thinker_formatter


def user_coordinator_node(resources, headless=False):
    """UserCoordinator 可调用对象工厂。

    Args:
        resources: LLMResources 实例
        headless: True 时禁用终端输出（CLI 模式）
    """
    sops_df = resources.sops_df
    valid_sop_ids = set(sops_df["SOP_ID"].tolist())
    _console = None if headless else Console()

    def coordinator(state: dict) -> dict:
        user_message = state.get("user_instruction", "")
        conversation_history = state.get("conversation_history", "")
        current_dialogue = state.get("current_dialogue", [])
        execution_history = state.get("execution_history", "")

        from utils.sop_loader import build_sop_library_from_ids
        sop_ids = state.get("sop_ids", [])
        sop_library = build_sop_library_from_ids(sops_df, sop_ids)

        def build_input(s):
            return (
                f"USER_MESSAGE: {user_message}\n\n"
                f"CURRENT_DIALOGUE: {dialogue_to_text(current_dialogue) or 'None'}\n\n"
                f"CONVERSATION_HISTORY: {conversation_history or 'None'}\n\n"
                f"EXECUTION_HISTORY: {execution_history or 'None'}\n\n"
                f"SOP_LIBRARY:\n{sop_library}\n"
            )

        from validator.UserCoordinatorValidator import validate_coordinator_output

        def map_result(parsed, thinker_tokens, **ctx):
            tool_call = parsed.get("tool_call", "")
            if tool_call and tool_call.upper() != "NONE":
                matched_sop_id = tool_call.split("(")[0].strip()
            else:
                matched_sop_id = ""
            return {
                "chat_message": parsed.get("chat_message", ""),
                "matched_sop_id": matched_sop_id,
                "tool_call": tool_call if tool_call.upper() != "NONE" else "",
                "thinker_input_tokens": thinker_tokens.get("input", 0) if thinker_tokens else 0,
            }

        return run_thinker_formatter(
            state=state,
            resources=resources,
            thinker_llm_key="user_coordinator_thinker",
            formatter_llm_key="all_formatter",
            thinker_prompt_key="user_coordinator_thinker",
            formatter_prompt_key="user_coordinator_formatter",
            node_name="UserCoordinator",
            build_thinker_input=build_input,
            validate_output=validate_coordinator_output,
            map_result=map_result,
            fallback_result={
                "chat_message": "抱歉，我暂时无法理解您的需求。能换个方式描述一下吗？",
                "matched_sop_id": "",
                "tool_call": "",
            },
            thinker_label="Thinker",
            formatter_label="Formatter",
            console=_console,
            headless=headless,
            formatter_buffer_interval=2.0,
            valid_sop_ids=valid_sop_ids,
        )

    return coordinator
