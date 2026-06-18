"""ChatCompactor LLM 节点。

对对话上下文进行压缩，由 /compact 命令或 auto-compact 触发。
Thinker (temp 0.4) + Formatter (temp 0.0) 双阶段，输出 CONVERSATION_SUMMARY 单字段。
"""

from rich.console import Console
from repl.dialogue_utils import dialogue_to_text
from llm_nodes.thinker_formatter_runner import run_thinker_formatter


def chat_compactor_node(resources):
    """ChatCompactor 可调用对象工厂。"""

    _console = Console()

    def compact_chat(state: dict) -> dict:
        user_message = state.get("user_instruction", "")
        current_dialogue = state.get("current_dialogue", [])
        conversation_history = state.get("conversation_history", "")
        compact_requirement = state.get("chat_compact_requirement", "")

        def build_input(s):
            return (
                f"COMPACT_REQUIREMENT: {compact_requirement or 'None'}\n\n"
                f"USER_MESSAGE: {user_message}\n\n"
                f"CURRENT_DIALOGUE: {dialogue_to_text(current_dialogue) or 'None'}\n\n"
                f"CONVERSATION_HISTORY: {conversation_history or 'None'}\n"
            )

        from validator.ChatCompactorValidator import validate_chat_compactor_output

        def map_result(parsed, thinker_tokens, **ctx):
            return {
                "chat_conversation_summary": parsed.get("conversation_summary", ""),
            }

        return run_thinker_formatter(
            state=state,
            resources=resources,
            thinker_llm_key="chat_compactor_thinker",
            formatter_llm_key="all_formatter",
            thinker_prompt_key="chat_compactor_thinker",
            formatter_prompt_key="chat_compactor_formatter",
            node_name="ChatCompactor",
            build_thinker_input=build_input,
            validate_output=validate_chat_compactor_output,
            map_result=map_result,
            fallback_result={
                "conversation_summary": "User conversation occurred but could not be summarized.",
            },
            console=_console,
        )

    return compact_chat
