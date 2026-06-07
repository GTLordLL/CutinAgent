import os

_CURRENT = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_CURRENT)


def load_prompt_file(file_path="./prompts/tool_selector.md"):
    """通用加载函数，读取 Prompt 模板内容。非绝对路径基于 __file__ 拼接。"""
    if not os.path.isabs(file_path):
        file_path = os.path.join(_PROJECT_ROOT, file_path.lstrip("./"))
    try:
        if not os.path.exists(file_path):
            print(f"Error: Prompt file not found at {file_path}")
            return ""

        with open(file_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        print(f"Error loading Prompt: {e}")
        return ""
