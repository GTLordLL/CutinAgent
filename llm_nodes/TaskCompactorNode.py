"""TaskCompactor LLM 节点。

在 SOP 执行完成后运行，评估执行结果并生成 dialogue 和 execution 两维度摘要。
Thinker (temp 0.4) + Formatter (temp 0.0) 双阶段。
"""

from rich.console import Console
from repl.dialogue_utils import dialogue_to_text
from llm_nodes.thinker_formatter_runner import run_thinker_formatter


def task_compactor_node(resources, headless=False):
    """TaskCompactor 可调用对象工厂。

    Args:
        resources: LLMResources 实例
        headless: True 时完全静默，不输出任何内容到终端
    """
    _console = None if headless else Console()

    def compact_task(state: dict) -> dict:
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

        def build_input(s):
            return (
                f"USER_MESSAGE: {user_message}\n\n"
                f"CURRENT_DIALOGUE: {dialogue_to_text(current_dialogue) or 'None'}\n\n"
                f"CONVERSATION_HISTORY: {conversation_history or 'None'}\n\n"
                f"CURRENT_ACTION: {current_action}\n\n"
                f"LONG_TERM_INTENT: {long_term_intent or 'None'}\n\n"
                f"LATEST_EXECUTION_RESULT:\n{latest_execution}\n\n"
                f"EXECUTION_HISTORY: {execution_history or 'None'}\n"
            )

        from validator.CompactorValidator import validate_compactor_output

        def map_result(parsed, thinker_tokens, **ctx):
            return {
                "compactor_evaluation": parsed.get("evaluation", ""),
                "compactor_conversation_summary": parsed.get("conversation_summary", ""),
                "compactor_execution_summary": parsed.get("execution_summary", ""),
            }

        return run_thinker_formatter(
            state=state,
            resources=resources,
            thinker_llm_key="compactor_thinker",
            formatter_llm_key="all_formatter",
            thinker_prompt_key="compactor_thinker",
            formatter_prompt_key="compactor_formatter",
            node_name="TaskCompactor",
            build_thinker_input=build_input,
            validate_output=validate_compactor_output,
            map_result=map_result,
            fallback_result={
                "evaluation": "Unable to evaluate the SOP execution due to output parsing failure.",
                "conversation_summary": "User interaction occurred but could not be summarized.",
                "execution_summary": "SOP executed but results could not be compacted.",
            },
            thinker_label="Thinker",
            formatter_label="Formatter",
            console=_console,
            headless=headless,
        )

    return compact_task
