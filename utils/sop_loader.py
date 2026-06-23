"""SOP Markdown 文件加载与索引构建。"""
import os
import re

from parsers.tool_call import _build_tool_signature


def build_sop_library_index(sops_df) -> str:
    """从CSV索引构造 SOP 匹配用的精简文本（Python 函数签名格式，含 Func_Desc + 参数签名）。"""
    lines = []
    for _, row in sops_df.iterrows():
        lines.append(_build_tool_signature(row))
    return "\n".join(lines)


def build_sop_library_from_ids(sops_df, sop_ids: list[str]) -> str:
    """根据指定的 sop_ids 列表构造 SOP 匹配文本（Python 函数签名格式）。

    只输出 sop_ids 中存在的 SOP；不存在的 ID 静默跳过。
    格式：SOP_ID(params): \"\"\"Func_Desc — param_desc\"\"\"
    """
    if not sop_ids:
        return (
            "No executable SOPs are available. "
            "You may chat with the user and suggest SOP recommendations."
        )

    ids_set = set(sop_ids)
    lines = []
    for _, row in sops_df.iterrows():
        sid = row["SOP_ID"]
        if sid in ids_set:
            lines.append(_build_tool_signature(row))
    return "\n".join(lines)


def load_sop_markdown(sop_id: str, sop_dir: str,
                      valid_tool_ids: set | None = None) -> dict:
    """加载单个 SOP 的完整 markdown 文件并解析各字段。
    返回: {"objective": ..., "description": ..., "plan_steps": ..., "tools_required": ..., "keywords": ...}
    若 valid_tool_ids 不为 None，则对 Plan_Steps 执行严格 DSL 校验。
    """
    file_path = os.path.join(sop_dir, f"{sop_id}.md")
    if not os.path.exists(file_path):
        print(f"[警告] SOP 文件不存在: {file_path}")
        return {}

    with open(file_path, "r", encoding="utf-8") as f:
        content = f.read()

    def extract_section(text: str, heading: str) -> str:
        """提取 ## heading 之后的内容，直到下一个 ## 或文件尾。"""
        pattern = rf'##\s+{heading}\s*\n(.*?)(?=\n##\s|\Z)'
        match = re.search(pattern, text, re.DOTALL)
        if match:
            return match.group(1).strip()
        return ""

    plan_steps = extract_section(content, "Plan_Steps")
    retry_limit_text = extract_section(content, "Retry_Limit")

    # SOP Plan_Steps 格式校验
    if valid_tool_ids is not None and plan_steps:
        from validator.SopSpecChecker import check_sop_plan_steps
        errors = check_sop_plan_steps(plan_steps, valid_tool_ids)
        if errors:
            error_msg = "\n".join(
                f"  L{e.line_number} S{e.step_number}: [{e.severity}] {e.message}"
                for e in errors
            )
            raise ValueError(
                f"SOP '{sop_id}' Plan_Steps 格式校验失败:\n{error_msg}"
            )

    # SOP Retry_Limit 校验
    if valid_tool_ids is not None:
        from validator.SopSpecChecker import check_retry_limit
        errors = check_retry_limit(retry_limit_text)
        if errors:
            error_msg = "\n".join(
                f"  [{e.severity}] {e.message}"
                for e in errors
            )
            raise ValueError(
                f"SOP '{sop_id}' Retry_Limit 校验失败:\n{error_msg}"
            )

    return {
        "objective": extract_section(content, "Objective"),
        "description": extract_section(content, "Description"),
        "plan_steps": plan_steps,
        "tools_required": extract_section(content, "Tools_Required"),
        "keywords": extract_section(content, "Keywords"),
        "exception_handling": extract_section(content, "Global_Exception_Handling"),
        "retry_limit": extract_section(content, "Retry_Limit"),
    }
