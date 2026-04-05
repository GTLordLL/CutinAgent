from typing import List, TypedDict

class SelectorInput(TypedDict):
    user_instruction: str

class SelectorOutput(TypedDict):
    selected_tid_list: List[str]