from langgraph.graph import StateGraph, END
from graph.OverallState import OverallState
from utils.LLMResources import LLMResources
from llm_nodes.SopExecutionSchedulerNode import sop_execution_scheduler_node
from data_nodes.ProgressUpdater import progress_updater_node
from data_nodes.ToolExecutor import tool_executor_node


def route_after_scheduler(state: OverallState):
    """Scheduler 后的条件路由：ONGOING → 执行工具，其余 → 结束."""
    status = state.get("task_status", "ONGOING")
    if status == "ONGOING":
        return "tool_executor"
    return END


def build_graph(resources: LLMResources):
    workflow = StateGraph(OverallState)

    # 注册节点（SOP 执行内循环）
    workflow.add_node("sop_execution_scheduler", sop_execution_scheduler_node(resources))
    workflow.add_node("tool_executor", tool_executor_node)
    workflow.add_node("progress_updater", progress_updater_node)

    # 入口：直接从 Scheduler 开始
    workflow.set_entry_point("sop_execution_scheduler")

    # Scheduler 后：ONGOING → 执行工具，FINISH/ERROR/INTERRUPT → 结束
    workflow.add_conditional_edges(
        "sop_execution_scheduler",
        route_after_scheduler,
        {
            "tool_executor": "tool_executor",
            END: END,
        }
    )

    # 工具执行 → 进度更新
    workflow.add_edge("tool_executor", "progress_updater")

    # 进度更新后 → 无条件回到 Scheduler
    workflow.add_edge("progress_updater", "sop_execution_scheduler")

    return workflow.compile()
