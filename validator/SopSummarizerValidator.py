"""SopSummarizer 输出校验器。

校验单字段：SUMMARY（纯文本，非空，≤500 字符）。
"""


def validate_sop_summary(raw_output: str) -> tuple:
    """校验 SopSummarizer 的输出。

    Args:
        raw_output: LLM 的原始输出文本。

    Returns:
        (is_valid, error_reason, parsed_dict)
        parsed_dict keys: summary
    """
    text = raw_output.strip()

    if not text:
        return (False, "SUMMARY 不能为空", {})

    if len(text) > 500:
        return (False, f"SUMMARY 超过 500 字符限制（当前 {len(text)} 字符）", {})

    return (True, "", {"summary": text})
