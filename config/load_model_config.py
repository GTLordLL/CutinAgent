import json
import os

def load_model_config(config_path="./config/model_config.json"):
    try:
        if not os.path.exists(config_path):
            print(f"Error: Config file not found at {config_path}")
            return None
            
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading Model Config: {e}")
        return None

def get_generation_params(config):
    if config is None: return {}
    return config.get("generation_options", {})

def get_model_name(config):
    if config is None: return "default-model"
    return config.get("model_name", "default-model")

def get_ollama_url():
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

# --- 测试代码 ---
if __name__ == "__main__":
    config = load_model_config()
    print(get_model_name(config))
    print(get_generation_params(config))