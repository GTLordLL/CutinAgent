import json
import os

def load_model_config(config_path="./config/model_config.json"):
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
