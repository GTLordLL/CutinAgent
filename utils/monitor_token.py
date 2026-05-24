def monitor_token_usage(response, total_limit=8192, silent=False):
    usage = getattr(response, 'usage_metadata', {}) or {}

    prompt_tokens = usage.get("input_tokens", 0)
    completion_tokens = usage.get("output_tokens", 0)
    total_tokens = usage.get("total_tokens", 0)

    usage_percent = (total_tokens / total_limit) * 100

    if not silent:
        print(f"[Tokens Monitor] Input: {prompt_tokens} | Output: {completion_tokens}")
        print(f"[Tokens Usage] Total: {total_tokens}/{total_limit} ({usage_percent:.1f}%)")

    if total_tokens > total_limit * 0.9:
        if not silent:
            print(f"⚠️  WARNING: Context window nearly full ({total_tokens}/{total_limit})!")
    elif total_tokens == 0:
        if not silent:
            print("❓  NOTICE: Usage metadata is empty. Check if the provider supports token tracking.")

    return {
        "input": prompt_tokens,
        "output": completion_tokens,
        "total": total_tokens,
        "is_near_limit": total_tokens > total_limit * 0.9
    }
