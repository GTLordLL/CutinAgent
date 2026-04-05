from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage, BaseMessage
from tools.load_tools import get_tools_for_dag_design
from formatter.DAGValidator import validate_workflow_dag
from dto.ArchitectSchema import ArchitectInput, ArchitectOutput
import pandas as pd
from utils.extract_pure_dag import extract_pure_dag


class WorkflowArchitectNode:
    def __init__(self, llm: ChatOllama, prompt: str, tools_df: pd.DataFrame):
        # 依赖注入：直接使用传入的成品
        self.llm = llm
        self.base_prompt = prompt
        self.tools_df = tools_df
        self.max_retries = 3
        

    def __call__(self, state: ArchitectInput) -> ArchitectOutput:
        user_instruction = state["user_instruction"]
        selected_tid_list = state["selected_tid_list"]

        dag_tools_context = get_tools_for_dag_design(self.tools_df, selected_tid_list)
        if not dag_tools_context and not selected_tid_list:
            return {"workflow_dag": "ERROR: No tools provided to design a workflow."}
        
        # 4. 组装最终 Prompt
        full_system_prompt = f"{self.base_prompt}\n\nTOOL_LIST:\n{dag_tools_context}\n"
        messages: list[BaseMessage] = [SystemMessage(content=full_system_prompt)]
        
        if state.get("bad_workflow_dag") and state.get("reason"):
            retry_context = (
                f"Your previous attempt was REJECTED by the Semantic Auditor.\n"
                f"PREVIOUS_INSTRUCTION: {user_instruction}\n"
                f"REJECTED_DAG:\n{state['bad_workflow_dag']}\n"
                f"REASON FOR FAILURE: {state['reason']}\n"
                f"Please reflect on the error and generate a logic-corrected WORKFLOW_DAG now."
            )
            messages.append(HumanMessage(content=retry_context))
            print(retry_context)
        else:
            # 正常第一次尝试
            messages.append(HumanMessage(content=f"USER_INSTRUCTION: {user_instruction}"))

        # 打印输入到模型的完整上下文 ---
        print("\n" + "="*30 + " LLM INPUT START " + "="*30)
        print(f"USER_INSTRUCTION: {user_instruction}")
        print("="*31 + " LLM INPUT END " + "="*31 + "\n")

        retries = 0
        total_limit = 8192
        while retries < self.max_retries:
            try:
                # 6. 调用模型
                response = self.llm.invoke(messages)
                workflow_raw = str(response.content)
    
                # Token 监测逻辑 
                usage = getattr(response, 'usage_metadata', {}) or {}
                prompt_tokens = usage.get("input_tokens", 0)
                completion_tokens = usage.get("output_tokens", 0)
                total_tokens = usage.get("total_tokens", 0)
                print(f"[Token Monitor] Input: {prompt_tokens} | Output: {completion_tokens} | Total: {total_tokens}/{total_limit}")
                # 如果当前占用已经接近极限，打印警告
                if total_tokens > total_limit * 0.9:
                    print(f"⚠️ WARNING: Context window nearly full ({total_tokens}/{total_limit})!")
                # 打印原始输出方便调试
                print(f"\n--- [Attempt {retries+1}] LLM Raw Output: \n{workflow_raw}\n ---")

                pure_dag = extract_pure_dag(workflow_raw)

                # 7. 使用编译器进行校验 ---
                is_valid, result = validate_workflow_dag(pure_dag, set(state["selected_tid_list"]))
                
                if is_valid:
                    print(f"--- [Architect Success] DAG validated. Steps: {len(result)} ---")
                    return {"workflow_dag": pure_dag}
                else:
                    # 如果校验失败，result 此时是错误描述字符串
                    retries += 1
                    error_msg = f"LINTER ERROR: {result}\nPlease fix the DAG syntax or logic and try again."
                    print(f"--- [Architect Retry {retries}] {result} ---")
                    
                    messages.append(AIMessage(content=pure_dag))
                    messages.append(HumanMessage(content=error_msg))
                
            except Exception as e:
                print(f"Critical Error in WorkflowArchitectNode: {e}")
                return {"workflow_dag": f"System Failure during DAG design: {str(e)}"}

        # 超过重试次数
        return {"workflow_dag": "FAILED_TO_GENERATE_VALID_DAG"}

# --- 测试代码 ---
if __name__ == "__main__":
    print()