import pandas as pd
from typing import List

def load_tools_df(csv_path="./tools/tools.csv"):
    """通用加载函数"""
    try:
        return pd.read_csv(csv_path)
    except Exception as e:
        print(f"Error loading CSV: {e}")
        return None

def get_tools_for_discovery(df):
    if df is None: return ""
    selected_df = df[['Tool_ID', 'Pre_Req', 'Keywords', 'Func_Desc']]
    # index=False 去掉行索引，返回 CSV 格式的字符串
    return selected_df.to_csv(index=False)

def get_tools_for_dag_design(df: pd.DataFrame, selected_tools: List[str]) -> str:
    if df is None or not selected_tools:
        return ""
    # 1. 使用 isin 过滤出目标 ID 的行
    # 2. 只选取设计师关心的 4 个核心字段
    filtered_df = df[df['Tool_ID'].isin(selected_tools)][['Tool_ID', 'Pre_Req', 'Args_Schema', 'Yields']]
    if filtered_df.empty:
        return ""
    # 3. 返回 CSV 格式字符串（去掉索引）
    return filtered_df.to_csv(index=False)

# --- 测试逻辑 ---
if __name__ == "__main__":
    # 1. 模拟一个功能完整的全量工具表 (包含 Args_Schema 和 Yields)
    mock_data = {
        'Tool_ID': ['free', 'ps', 'df', 'ls', 'cat'],
        'Pre_Req': ['', '', '', '', ''],
        'Keywords': ['memory', 'process', 'disk', 'list', 'read'],
        'Func_Desc': ['Check RAM', 'List tasks', 'Check disk', 'List files', 'Read file'],
        'Args_Schema': [
            '{}', 
            '{"sort": "cpu|mem"}', 
            '{"path": "string"}', 
            '{"dir": "string"}', 
            '{"file": "string"}'
        ],
        'Yields': [
            'mem_stats', 
            'proc_list', 
            'disk_usage', 
            'file_list', 
            'file_content'
        ]
    }
    full_df = pd.DataFrame(mock_data)

    print("--- [Step 1] Full Tools DataFrame Created ---")
    
    # 2. 模拟 ToolSelectorNode 的输出结果
    # 假设用户想看内存和进程，筛选器选出了这两个 ID
    mock_selected_tools = ['free', 'ps']
    print(f"--- [Step 2] Selected Tools from SelectorNode: {mock_selected_tools} ---")

    # 3. 测试获取设计师所需的元数据
    dag_metadata = get_tools_for_dag_design(full_df, mock_selected_tools)

    print("\n--- [Step 3] Metadata for WorkflowArchitectNode ---")
    if dag_metadata:
        print(dag_metadata)
    else:
        print("Empty Metadata! Check if Tool_IDs exist in DataFrame.")

    # 4. 边界测试：传入不存在的 ID
    print("\n--- [Step 4] Edge Case: Unknown Tool ID ---")
    edge_case_metadata = get_tools_for_dag_design(full_df, ['unknown_tool_99'])
    print(f"Result for unknown ID (Expected empty CSV header): \n{edge_case_metadata}")