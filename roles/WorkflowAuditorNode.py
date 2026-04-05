import pandas as pd
from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dto.AuditorSchema import AuditorInput, AuditorOutput
from formatter.LogicValidator import validate_dag_logic
from utils.extract_semantic import extract_semantic_chain

class WorkflowAuditorNode:
    def __init__(self, llm: ChatOllama, prompt: str, tools_df: pd.DataFrame):
        # 依赖注入：直接使用传入的成品
        self.llm = llm
        self.base_prompt = prompt
        self.tools_df = tools_df
        self.max_retries = 3


    def __call__(self, state: AuditorInput) -> AuditorOutput:
        user_instruction = state["user_instruction"]
        workflow_dag = state["workflow_dag"]

        # 1. 提取语义链条
        semantic_chain = extract_semantic_chain(workflow_dag)

        # 2. 构造更清晰的 HumanMessage 内容
        audit_payload = (
            f"USER_INSTRUCTION:\n{user_instruction}\n\n"
            f"SEMANTIC_CHAIN:\n{semantic_chain}\n\n{workflow_dag}\n\n"
        )

        messages = [
            SystemMessage(content=self.base_prompt),
            HumanMessage(content=audit_payload)
        ]

        # 打印输入到模型的完整上下文 ---
        print("\n" + "="*30 + " LLM INPUT START " + "="*30)
        print(audit_payload)
        print("="*31 + " LLM INPUT END " + "="*31 + "\n")
        # ---------------------------------------

        retries = 0
        total_limit = 8192
        while retries < self.max_retries:
            try:
                response = self.llm.invoke(messages)
                raw_content = str(response.content)
    
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
                print(f"\n--- [Attempt {retries+1}] LLM Raw Output: \n{raw_content}\n ---")

               # 3. 校验并解析输出格式
                is_success, status, reason = validate_dag_logic(raw_content)

                if is_success:
                    print(f"--- [Audit Finished] Result: {status} | Reason: {reason} ---")
                    return {"result": is_success, "reason": reason}
                
                # 如果格式不对，计入重试
                retries += 1
                messages.append(AIMessage(content=raw_content))
                messages.append(HumanMessage(content="FORMAT ERROR: Please use '[RESULT] | [REASON]' format strictly."))

            except Exception as e:
                print(f"Critical Error in WorkflowAuditorNode: {e}")
                retries += 1

        return {"result": False, "reason": "Auditor failed after maximum retries."}


# --- 测试代码 ---
if __name__ == "__main__":
    print()