import json
import os

# user/config/ 下，往上 3 级到项目根目录
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def load_model_config(config_path="./user/config/model_config.json"):
    if not os.path.isabs(config_path):
        config_path = os.path.join(_PROJECT_ROOT, config_path.lstrip("./"))
    try:
        if not os.path.exists(config_path):
            return None
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading Model Config: {e}")
        return None


def get_ollama_url():
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
