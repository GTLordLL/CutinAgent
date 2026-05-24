import re


def validate_sop_id(raw_output: str, valid_sop_ids: set) -> tuple:
    """
    验证 Formatter 输出的 SOP_ID 是否合法。
    返回: (is_valid, error_reason, cleaned_sop_id)
    """
    cleaned = raw_output.strip().replace("#", "").replace("`", "").replace("*", "").replace('"', "").replace("'", "")

    # 去掉可能的 markdown 代码块
    cleaned = re.sub(r'^```[a-z]*\s*', '', cleaned)
    cleaned = re.sub(r'\s*```$', '', cleaned)

    # 提取 SOP_ID（允许大写蛇形命名和下划线）
    match = re.search(r'([A-Z][A-Z0-9_]+)', cleaned)
    if not match:
        return False, f"未找到有效的 SOP_ID 格式，输出内容: '{cleaned[:80]}'", ""

    sop_id = match.group(1)
    if sop_id not in valid_sop_ids:
        return False, f"SOP_ID '{sop_id}' 不在有效 SOP 列表中", ""

    return True, "", sop_id
