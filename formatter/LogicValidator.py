

def validate_dag_logic(llm_raw_output: str) -> tuple[bool, str, str]:
    clean_output = llm_raw_output.strip().replace("**", "")
    if "|" in clean_output:
        parts = [p.strip() for p in clean_output.split("|", 1)]
        status = "PASS" if "PASS" in parts[0].upper() else "FAIL"
        return True, status, parts[1]
    
    # 兜底逻辑：如果模型没按格式出牌，尝试搜索关键字
    if "PASS" in clean_output.upper()[:10]:
        return True, "PASS", clean_output
    if "FAIL" in clean_output.upper()[:10]:
        return True, "FAIL", clean_output
        
    return False, "FAIL", f"Raw output format error: {clean_output}"
