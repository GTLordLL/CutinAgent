from typing import List, TypedDict

class ArchitectInput(TypedDict):
    user_instruction: str
    selected_tid_list: List[str]
    result: bool
    reason: str
    bad_workflow_dag: str

class ArchitectOutput(TypedDict):
    workflow_dag: str