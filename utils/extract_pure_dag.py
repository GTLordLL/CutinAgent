import re

def extract_pure_dag(text: str) -> str:
    """
    只提取模型回复中最后一个 WORKFLOW_DAG 部分，过滤掉多余的解释。
    """
    # 查找最后一个出现 WORKFLOW_DAG: 的位置
    # 这样即使模型在重试时输出了多个 DAG 块，我们也只取最终修正后的那个
    marker = "WORKFLOW_DAG:"
    last_idx = text.rfind(marker)
    
    if last_idx == -1:
        return text.strip() # 如果没找到标记，返回原样（由后续 Linter 处理）

    # 从标记处截取到最后
    pure_content = text[last_idx:].strip()
    
    # 如果模型在 DAG 后面又输出了类似 TOOL_LIST: 或其他解释，将其截断
    # 假设 DAG 之后不应该出现其他以大写字母加冒号结尾的行
    other_block_marker = re.search(r"\n[A-Z_]+:(\s|$)", pure_content)
    if other_block_marker:
        pure_content = pure_content[:other_block_marker.start()].strip()
        
    return pure_content