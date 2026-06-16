"""Problem Analyzer LLM 节点（v0.2）。

在 UserCoordinator 之前运行，自主调用信息采集类工具收集实时数据，
归纳当前状态，推断用户意图。Thinker (temp 0.4) + Formatter (temp 0.0) 双阶段。

输出四字段：CURRENT_STATE, CONFIDENCE, TOOL_CALL, MY_UNDERSTANDING
"""

from rich.console import Console
from repl.dialogue_utils import dialogue_to_text
from parsers.tool_call import _build_tool_signature
from llm_nodes.thinker_formatter_runner import run_thinker_formatter


def problem_analyzer_node(resources, headless=False):
    """Problem Analyzer 可调用对象工厂。

    Args:
        resources: LLMResources 实例
        headless: True 时禁用终端输出（CLI 模式）
    """
    tools_df = resources.tools_df
    _console = None if headless else Console()

    # 预构建 GATHERED_TOOLS 文本：仅 Tool_Type == "gather" 的工具
    gather_df = tools_df[tools_df["Tool_Type"] == "gather"]
    _gathered_tools_lines = []
    for _, row in gather_df.iterrows():
        _gathered_tools_lines.append(_build_tool_signature(row))
    GATHERED_TOOLS_TEXT = "\n".join(_gathered_tools_lines)

    def analyzer(state: dict) -> dict:
        user_message = state.get("user_instruction", "")
        conversation_history = state.get("conversation_history", "")
        current_dialogue = state.get("current_dialogue", [])
        execution_history = state.get("execution_history", "")

        def build_input(s):
            return (
                f"USER_MESSAGE: {user_message}\n\n"
                f"CURRENT_DIALOGUE: {dialogue_to_text(current_dialogue) or 'None'}\n\n"
                f"CONVERSATION_HISTORY: {conversation_history or 'None'}\n\n"
                f"EXECUTION_HISTORY: {execution_history or 'None'}\n\n"
                f"GATHERED_TOOLS:\n{GATHERED_TOOLS_TEXT}\n"
            )

        from validator.ProblemAnalyzerValidator import validate_analyzer_output

        def map_result(parsed, thinker_tokens):
            return {
                "analyzer_current_state": parsed.get("current_state", ""),
                "analyzer_confidence": parsed.get("confidence", "low"),
                "analyzer_tool_call": parsed.get("tool_call", ""),
                "analyzer_my_understanding": parsed.get("my_understanding", ""),
                "thinker_input_tokens": thinker_tokens.get("input", 0) if thinker_tokens else 0,
            }

        return run_thinker_formatter(
            state=state,
            resources=resources,
            thinker_llm_key="problem_analyzer_thinker",
            formatter_llm_key="all_formatter",
            thinker_prompt_key="problem_analyzer_thinker",
            formatter_prompt_key="problem_analyzer_formatter",
            node_name="ProblemAnalyzer",
            build_thinker_input=build_input,
            validate_output=validate_analyzer_output,
            map_result=map_result,
            fallback_result={
                "current_state": "无法解析用户意图，需人工确认。",
                "confidence": "low",
                "tool_call": "",
                "my_understanding": "",
            },
            thinker_label="Analyzer Thinker",
            formatter_label="Analyzer Formatter",
            console=_console,
            headless=headless,
            formatter_buffer_interval=2.0,
        )

    return analyzer
