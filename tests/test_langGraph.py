from typing import Annotated, TypedDict, Literal
from langchain_ollama import ChatOllama
from langgraph.graph import StateGraph, START, END

# 1. 定义状态
class State(TypedDict):
    content: str      # 初稿内容
    critique: str     # 评价意见
    iterations: int   # 迭代次数，防止无限循环
    is_ok: bool       # 是否合格

# 2. 初始化模型
llm = ChatOllama(model="qwen2.5:7b", base_url="http://localhost:11434")

# 3. 节点 A：生成器 (Generator)
def generator_node(state: State):
    prompt = "请写一段关于‘人工智能未来’的短文。要求逻辑严密。"
    # 使用 .get 确保安全，虽然 TypedDict 此时已经初始化
    critique = state.get("critique", "")
    if critique:
        prompt += f"\n\n注意以下修改建议：{critique}"
    
    response = llm.invoke(prompt)
    # 注意：LangGraph 会自动合并字典，所以这里只需返回更新的部分
    return {
        "content": str(response.content), 
        "iterations": state.get("iterations", 0) + 1
    }

# 4. 节点 B：审核员 (Reflector)
def reflector_node(state: State):
    content = state.get("content", "")
    prompt = f"你是审核员，请评价以下内容。如果内容逻辑严密且超过100字，回复'合格'。否则请给出具体的修改建议。\n\n内容：{content}"
    
    response = llm.invoke(prompt)
    feedback = str(response.content)
    
    is_ok = "合格" in feedback
    return {"critique": feedback, "is_ok": is_ok}

# 5. 定义条件边逻辑 (Router)
def should_continue(state: State) -> Literal["generate", "__end__"]:
    if state.get("is_ok") or state.get("iterations", 0) >= 3:
        return "__end__"
    return "generate"

# 6. 构建图
workflow = StateGraph(State)

workflow.add_node("generate", generator_node)
workflow.add_node("reflect", reflector_node)

workflow.add_edge(START, "generate")
workflow.add_edge("generate", "reflect")

# 添加条件边：从 reflect 出发，根据 should_continue 的返回值决定去向
workflow.add_conditional_edges(
    "reflect",
    should_continue,
    {
        "generate": "generate",
        "__end__": END
    }
)

# 7. 编译并运行
app = workflow.compile()

initial_input: State = {
    "content": "",
    "critique": "",
    "iterations": 0,
    "is_ok": False
}

result = app.invoke(initial_input)

print(f"--- 最终迭代次数: {result['iterations']} ---")
print(f"--- 最终内容 ---\n{result['content']}")