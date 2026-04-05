import re

def extract_semantic_chain(workflow_dag: str) -> str:
    """
    从 WORKFLOW_DAG 中提取所有注释并串联成语义链条。
    输入示例: 1. [free] -> ... # 获取内存状态
    输出示例: 1. 获取内存状态 -> 2. 提取关键指标
    """
    # 匹配模式：数字序号 + [工具名] + ... + # 注释内容
    # 使用 re.MULTILINE 确保能逐行处理
    pattern = re.compile(r"^(?P<idx>\d+)\..*?#\s*(?P<comment>.*)$", re.MULTILINE)
    
    matches = pattern.finditer(workflow_dag)
    chain_steps = []
    
    for match in matches:
        idx = match.group("idx")
        comment = match.group("comment").strip()
        if comment:
            chain_steps.append(f"{idx}. {comment}")
    
    # 使用 ' -> ' 符号连接，形成逻辑链条感
    return " -> ".join(chain_steps) if chain_steps else "No semantic comments found."