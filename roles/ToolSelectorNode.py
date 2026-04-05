from langchain_ollama import ChatOllama
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from formatter.TIDListValidator import validate_tool_selection
from tools.load_tools import get_tools_for_discovery
from dto.SelectorSchema import SelectorInput, SelectorOutput
import pandas as pd

class ToolSelectorNode:
    def __init__(self, llm: ChatOllama, prompt: str, tools_df: pd.DataFrame):
        # 依赖注入：直接使用传入的成品
        self.llm = llm
        self.base_prompt = prompt
        self.tools_df = tools_df
        self.max_retries = 3
        # 提取所有合法的 Tool_ID 用于校验
        self.all_tool_ids = set(self.tools_df['Tool_ID'].tolist())
        

    def __call__(self, state: SelectorInput) -> SelectorOutput:
        user_instruction = state["user_instruction"]
        # 1. 动态生成上下文 (DATABASE_EXTRACT)
        discovery_csv = get_tools_for_discovery(self.tools_df)
        # 2. 组装 System Prompt
        full_system_prompt = f"{self.base_prompt}\n\nDATABASE_EXTRACT:\n{discovery_csv}\n"
        
        # 打印输入到模型的完整上下文 ---
        print("\n" + "="*30 + " LLM INPUT START " + "="*30)
        # print(full_system_prompt)
        print(f"USER_INSTRUCTION: {user_instruction}")
        print("="*31 + " LLM INPUT END " + "="*31 + "\n")
        # ---------------------------------------

        # 3. 构造消息队列
        messages = [
            SystemMessage(content=full_system_prompt),
            HumanMessage(content=f"USER_INSTRUCTION: {user_instruction}")
        ]
        
        retries = 0
        total_limit = 8192
        while retries < self.max_retries:
            try:
                # 4. 调用模型
                response = self.llm.invoke(messages)
                raw_output = response.content

                # --- 【测试专用：主动制造错误】 ---
                # if retries == 0:
                #     # 场景 1: 制造 Markdown 代码块错误
                #     # raw_output = "```csv\nfree,ps\n```" 
                #     
                #     # 场景 2: 制造自然语言废话错误
                #     # raw_output = "I have selected the following tools: free, ps"
                #     
                #     # 场景 3: 制造非法 ID 错误
                #     raw_output = "free, ps, unknown_tool_99"
                #     
                #     print(f"⚠️ [TEST MODE] Injected Fake Error: {raw_output}")
                # ---------------------------------
                
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
                print(f"\n--- [Attempt {retries+1}] LLM Raw Output: {raw_output} ---")

                # 5. 使用严苛校验器
                is_valid, result = validate_tool_selection(raw_output, self.all_tool_ids)
                if is_valid and isinstance(result, list):
                    # 校验通过，result 是合法的 ID 列表
                    print(f"--- [Success] Verified Tool List: {result} ---")
                    return {"selected_tid_list": result}
                else:
                    # 校验失败，构造反馈信息并重试
                    retries += 1
                    error_feedback = f"FORMAT ERROR: {result}\nYour last output was: '{raw_output}'. Please correct it and output ONLY the CSV list."
                    print(f"--- [Retry] Feedback sent to LLM: {result} ---")
                    
                    # 将错误的回答和报错信息加入上下文
                    messages.append(AIMessage(content=raw_output))
                    messages.append(HumanMessage(content=error_feedback))

            except Exception as e:
                print(f"Critical Error in ToolSelectorNode: {e}")
                return {"selected_tid_list": []}

        # 超过重试次数
        return {"selected_tid_list": []}

# --- 测试代码 ---
if __name__ == "__main__":
    print()