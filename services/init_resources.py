from config.load_model_config import load_model_config, get_generation_params, get_model_name, get_ollama_url
from prompts.load_prompts import load_prompt_file
from langchain_ollama import ChatOllama
from tools.load_tools import load_tools_df

def initialize_resources():
    # 1. 统一加载配置
    config = load_model_config()
    
    # 2. 统一初始化 LLM 客户端（单例思想）
    model_name = get_model_name(config)
    gen_params = get_generation_params(config)
    llm = ChatOllama(
        model=model_name,
        base_url=get_ollama_url(),
        **gen_params
    )
    
    # 3. 统一加载 Prompts 字典
    prompts = {
        "selector": load_prompt_file("./prompts/tool_selector.md"),
        "architect": load_prompt_file("./prompts/workflow_architect.md"),
        "auditor": load_prompt_file("./prompts/workflow_auditor.md")
    }

    tools_df = load_tools_df()
    
    return llm, prompts, config, tools_df
