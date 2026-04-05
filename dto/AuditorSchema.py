from typing import TypedDict

class AuditorInput(TypedDict):
    user_instruction: str
    workflow_dag: str

class AuditorOutput(TypedDict):
    result: bool
    reason: str
