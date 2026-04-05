import ollama

# 1. 定义一个模拟工具（Function）
def get_current_weather(city: str):
    # 实际应用中这里会调用 API，测试时我们只定义结构
    pass

def test_qwen_function_calling():
    model_name = "qwen2.5:7b"
    
    tools = [{
        'type': 'function',
        'function': {
            'name': 'get_current_weather',
            'description': '获取指定城市的实时天气情况',
            'parameters': {
                'type': 'object',
                'properties': {
                    'city': {'type': 'string', 'description': '城市名称'},
                },
                'required': ['city'],
            },
        },
    }]

    print(f"--- 重新测试模型: {model_name} ---")

    # 尝试使用更显式的 chat 调用
    response = ollama.chat(
        model=model_name,
        messages=[
            # 增加一个 system message 提示它可以使用工具
            {'role': 'system', 'content': 'You are a helpful assistant with tool-calling capabilities.'},
            {'role': 'user', 'content': '请帮我查一下上海的天气怎么样？'}
        ],
        tools=tools,
        options={
            "num_ctx": 12288,
            "temperature": 0  # 降低随机性，强制其遵循格式
        }
    )

    # 打印原始响应内容以便排查
    print(f"DEBUG - Raw Message: {response['message']}")

    if response['message'].get('tool_calls'):
        print("✅ 成功：Ollama 正确解析了 tool_calls！")
    else:
        print("⚠️ 提示：模型输出了内容但未触发结构化 tool_calls。")
        # 如果模型输出了 JSON 字符串，说明逻辑没问题，只是 SDK/版本解析问题
        content = response['message'].get('content', '')
        if '{"name":' in content:
            print("💡 结论：模型本身具备能力，但 Ollama 未能识别为 Tool 对象。请尝试更新 Ollama。")

if __name__ == "__main__":
    test_qwen_function_calling()