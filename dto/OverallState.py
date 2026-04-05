from typing import List, TypedDict

# --- 全局输出状态定义 ---
class OverallState(TypedDict):
    user_instruction: str
    # SelectorOutput
    selected_tid_list: List[str]
    
    # ArchitectOutput  
    workflow_dag: str              
    
    # AuditorOutput
    result: bool                   
    reason: str                    
    bad_workflow_dag: str