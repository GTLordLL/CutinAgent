import os
from dataclasses import dataclass
from typing import Any, Dict
import pandas as pd
from user.config.load_model_config import load_model_config, get_ollama_url
from utils.load_prompts import load_prompt_file
from utils.load_csv import load_csv_df
from utils.sop_loader import load_sop_markdown
from utils.llm_errors import check_ollama_connectivity
from langchain_ollama import ChatOllama


@dataclass
class LLMResources:
    llms: Dict[str, Any]
    default_llm: Any
    prompts: Dict[str, str]

    tools_df: pd.DataFrame

    sops_df: pd.DataFrame
    sop_dir: str

    def get_llm(self, model_key: str = ""):
        if model_key is None or model_key not in self.llms:
            return self.default_llm
        return self.llms[model_key]


def initialize_resources() -> LLMResources:
    # 1. 加载模型配置
    config = load_model_config()
    assert config is not None, "无法加载模型配置文件！"

    node_settings = config.get("nodes", {})
    default_node_name = config.get("default_node")

    # 2. 初始化 LLM 实例
    llms = {}
    base_url = get_ollama_url()

    for node_key, params in node_settings.items():
        current_params = params.copy()
        model_id = current_params.pop("model_id", "qwen3:4b-instruct_q8_8k")
        llms[node_key] = ChatOllama(
            model=model_id,
            base_url=base_url,
            **current_params
        )

    default_llm = llms.get(default_node_name)
    if default_llm is None and llms:
        default_llm = list(llms.values())[0]

    # 2.5 检测 Ollama 连通性（提前发现连接问题，避免后续大段报错）
    ok, msg = check_ollama_connectivity(base_url)
    if not ok:
        print(f"\n⚠️  {msg}")
        print("  请确认 Ollama 已启动后再执行操作。\n")

    # 3. 加载 Prompts
    prompts = {
        "user_coordinator_thinker": load_prompt_file("./prompts/user_coordinator/thinker.md"),
        "user_coordinator_formatter": load_prompt_file("./prompts/user_coordinator/formatter.md"),
        "problem_analyzer_thinker": load_prompt_file("./prompts/problem_analyzer/thinker.md"),
        "problem_analyzer_formatter": load_prompt_file("./prompts/problem_analyzer/formatter.md"),
        "compactor_thinker": load_prompt_file("./prompts/compactor/thinker.md"),
        "compactor_formatter": load_prompt_file("./prompts/compactor/formatter.md"),
        "sop_execution_scheduler_thinker": load_prompt_file("./prompts/sop_execution_scheduler/thinker.md"),
        "sop_execution_scheduler_formatter": load_prompt_file("./prompts/sop_execution_scheduler/formatter.md"),
        "sop_summarizer": load_prompt_file("./prompts/sop_summarizer.md"),
    }

    # 4. 加载工具和 SOP 索引
    tools_df = load_csv_df("tools/tools.csv")
    if tools_df is None:
        raise FileNotFoundError("致命错误：无法加载 tools/tools.csv")

    sops_df = load_csv_df("sop/sops.csv")
    if sops_df is None:
        raise FileNotFoundError("致命错误：无法加载 sop/sops.csv")

    sop_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sop")

    return LLMResources(
        llms=llms,
        default_llm=default_llm,
        prompts=prompts,
        tools_df=tools_df,
        sops_df=sops_df,
        sop_dir=sop_dir,
    )
