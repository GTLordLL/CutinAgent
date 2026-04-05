from langgraph.graph import StateGraph, START, END
from dto.OverallState import OverallState
from dto.SelectorSchema import SelectorInput, SelectorOutput
from dto.ArchitectSchema import ArchitectInput, ArchitectOutput
from dto.AuditorSchema import AuditorInput, AuditorOutput
from roles.ToolSelectorNode import ToolSelectorNode
from roles.WorkflowArchitectNode import WorkflowArchitectNode
from roles.WorkflowAuditorNode import WorkflowAuditorNode
from services.init_resources import initialize_resources
import time

# --- 路由逻辑：判断是否需要进入设计师节点 ---
def should_design_workflow(state: OverallState):
    # 使用安全的访问方式，并提供默认值
    selected = state.get("selected_tid_list", [])
    if not selected:
        return "summarizer"
    return "architect"

def route_after_audit(state: OverallState):
    """根据审计结果决定下一跳"""
    if state["result"]:
        print(f"✅ Audit Passed. Moving to Executor.")
        return "executor"
    else:
        print(f"❌ Audit Failed. Reason: {state['reason']}. Retrying Architect...")
        return "architect"

# 模拟 Executor 节点：它只是打印一下设计师的计划
def mock_executor(state: OverallState):
    print("\n--- [Mock Executor] Running ---")
    plan_preview = state.get('workflow_dag', "")
    print(f"Executing Plan: {plan_preview}...")
    return {"execution_results": "All commands executed successfully (Simulation)."}

# 模拟 Summarizer 节点：给出最终回复
def mock_summarizer(state: OverallState):
    print("\n--- [Mock Summarizer] Running ---")
    return {"messages": ["任务已完成，内存和进程状态已核查。"]}


# 1. 初始化图
workflow = StateGraph(OverallState)

# 1. 统一加载资源
llm_client, all_prompts, model_config, shared_tools_df = initialize_resources()
if shared_tools_df is None:
    raise ValueError("Critical: tools.csv not found!")

# 2. 实例化你的节点类
selector_instance = ToolSelectorNode(llm=llm_client, prompt=all_prompts["selector"], tools_df=shared_tools_df)
architect_instance = WorkflowArchitectNode(llm=llm_client, prompt=all_prompts["architect"], tools_df=shared_tools_df)
auditor_instance = WorkflowAuditorNode(llm=llm_client, prompt=all_prompts["auditor"], tools_df=shared_tools_df)

# 3. 将节点添加到图中，并绑定其专有的 Schema (DTO)
workflow.add_node(
    "selector", 
    selector_instance,
    input=SelectorInput,
    output=SelectorOutput
)# type: ignore

workflow.add_node(
    "architect", 
    architect_instance,
    input=ArchitectInput,
    output=ArchitectOutput
)# type: ignore

workflow.add_node(
    "auditor", 
    auditor_instance,
    input=AuditorInput,  
    output=AuditorOutput
)# type: ignore

# 将模拟节点加入图
workflow.add_node("executor", mock_executor)
workflow.add_node("summarizer", mock_summarizer)

# 4. 设置连接逻辑
workflow.add_edge(START, "selector")

# 使用条件边：决定是去设计师，还是直接去总结
workflow.add_conditional_edges(
    "selector",
    should_design_workflow,
    {
        "architect": "architect",
        "summarizer": "summarizer" # 假设这是你的兜底节点
    }
)

# 4. Architect 完工后必须经过审计
workflow.add_edge("architect", "auditor")

# 5. 【核心】审计员的条件分支：成功去执行，失败回设计师
workflow.add_conditional_edges(
    "auditor",
    route_after_audit,
    {
        "executor": "executor",
        "architect": "architect"  # 形成环路 (Re-design Loop)
    }
)

# 6. 后续收尾
workflow.add_edge("executor", "summarizer")
workflow.add_edge("summarizer", END)

# 5. 编译图
app = workflow.compile()

if __name__ == "__main__":
    # 1. 准备初始输入
    # 注意：这里的字段必须匹配你的 OverallState 定义
    user_query = "帮我分析一下当前系统负载情况。如果负载过高，请列出磁盘占用最大的前 3 个文件夹。"
    initial_input: OverallState = {
        "user_instruction": user_query,
        "selected_tid_list": [],      # 初始为空，由 Selector 填充
        "workflow_dag": "",        # 初始为空，由 Architect 填充
        "result": False,           # 审计结果
        "reason": "",              # 审计原因
        "bad_workflow_dag": "",    # 曾经失败的计划
    }

    print("\n" + "🚀" * 10 + " 系统启动：多 Agent 协作流水线 " + "🚀" * 10)
    print(f"用户指令: {user_query}")
    print("-" * 60)

    # 2. 运行图
    # 使用 stream 模式可以让你看到每一个节点的产出（增量更新）
    start_time = time.time()
    try:
        print("Starting workflow execution...")
        for event in app.stream(initial_input):
            if event:
            # event 是一个字典，key 是节点名称，value 是该节点返回的状态增量
                for node_name, output in event.items():
                    if output and isinstance(output, dict):
                        print(f"\n[节点完成]: {node_name}")
                        # 打印该节点产出的关键信息
                        if node_name == "selector":
                            print(f" -> 已选工具: {output.get('selected_tid_list')}")
                            print(f"用时: {time.time() - start_time:.2f} 秒")
                        elif node_name == "architect":
                            print(f" -> 计划生成完成 (长度: {len(output.get('workflow_dag', ''))} 字符)")
                            print(f"用时: {time.time() - start_time:.2f} 秒")
                        elif node_name == "auditor":
                            status = "✅ 通过" if output.get("result") else "❌ 失败"
                            print(f" -> 审计结果: {status}")
                            print(f"用时: {time.time() - start_time:.2f} 秒")
                            if not output.get("result"):
                                print(f" -> 失败原因: {output.get('reason')}")
                        elif node_name == "summarizer":
                            print(f" -> 最终回复: {output.get('messages')}")

        end_time = time.time()
        print("\n" + "=" * 20 + " 任务执行完毕 " + "=" * 20)
        print(f"总耗时: {end_time - start_time:.2f} 秒")

    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()