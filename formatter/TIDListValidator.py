import re

def validate_tool_selection(llm_output, all_tool_ids):
    # 1. 检查 Markdown 代码块
    if "```" in llm_output:
        return False, "CRITICAL ERROR: Do NOT wrap your output in Markdown code blocks (```). Output must be RAW text."
    # 2. 检查多行（通常是解释说明）
    if "\n" in llm_output.strip():
        return False, "ERROR: Multiple lines detected. Your output must be a single-line, comma-separated list."
    # 3. 检查非法字符/前缀 (关键修正：提前到 ID 拆分之前)
    # 允许：字母、数字、下划线、连字符、逗号、空格
    # 任何冒号(:)、感叹号(!)、括号() 都会被这里拦截
    if re.search(r"[^\w\s,\-]", llm_output):
         return False, "ERROR: Forbidden characters (like ':', '!', or explanations) detected. Output ONLY Tool_IDs separated by commas."
    # 4. 检查中文逗号
    if "，" in llm_output:
        return False, "ERROR: Chinese comma '，' detected. Use standard English comma ',' only."
    # 5. 尝试拆分并检查
    raw_ids = [s.strip() for s in llm_output.split(',') if s.strip()]
    
    if not raw_ids:
        return False, "ERROR: No Tool_IDs found in output."
    # 6. 校验 ID 是否存在于数据库
    invalid_ids = [tid for tid in raw_ids if tid not in all_tool_ids]
    if invalid_ids:
        # 如果走到这一步，说明格式是对的（没有非法符号），但 ID 写错了（幻觉）
        return False, f"ERROR: The following IDs do not exist in the [DATABASE_EXTRACT]: {invalid_ids}. Please verify the Tool_ID naming."
    return True, raw_ids


# --- 测试代码 ---
if __name__ == "__main__":
    print()