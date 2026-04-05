import re

def validate_workflow_dag(llm_output: str, allowed_tools: set):
    if "WORKFLOW_DAG:" not in llm_output:
        return False, "CRITICAL ERROR: Missing 'WORKFLOW_DAG:' header."
    
    dag_part = llm_output.split("WORKFLOW_DAG:")[-1].strip()
    lines = [line.strip() for line in dag_part.split('\n') if line.strip()]
    
    if not lines:
        return False, "ERROR: WORKFLOW_DAG is empty."

    parsed_steps = []
    defined_vars = set()
    step_indices = set()

    line_pattern = re.compile(
        r"^(?P<idx>\d+)\.\s+\[(?P<tool>\w+)\]\s+->\s+dep:\s+(?P<dep>None|[\d\s,]+)\s+\|\s+"
        r"(?:input:\s+(?P<input>[^|]+?)\s*\||prompt:\s+\"(?P<prompt>.*?)\"\s*\|)\s+"
        r"out:\s+(?P<out>\w+)\s+#\s+(?P<comment>.*)$"
    )

    for line in lines:
        match = line_pattern.match(line)
        if not match:
            return False, f"SYNTAX ERROR: Line '{line}' is invalid. Ensure format: [N]. [Tool] -> dep: N | input: V | out: V # comment"
        
        data = match.groupdict()
        idx = int(data['idx'])
        tool = data['tool']
        dep_raw = data['dep']
        raw_input = data['input'] if data['input'] is not None else ""
        prompt = data['prompt']
        out_var = data['out']
        comment = data['comment']
        # 1. 序号检查 
        if idx in step_indices:
            return False, f"LOGIC ERROR: Duplicate step index '{idx}'."
        step_indices.add(idx)
        # 2. 工具合法性检查
        if not (tool in allowed_tools or tool.startswith("try_")):
            return False, f"TOOL ERROR: [{tool}] not selected."

        # 3. 拓扑检查 
        dep_list = None
        if dep_raw != "None":
            try:
                dep_list = [int(d.strip()) for d in str(dep_raw).split(',') if d.strip()]
            except ValueError:
                return False, f"SYNTAX ERROR: Step {idx} has invalid dep format '{dep_raw}'."

            for dep_idx in dep_list:
                if dep_idx >= idx:
                    return False, f"TOPOLOGY ERROR: Step {idx} depends on future step {dep_idx}."
                if dep_idx not in step_indices:
                    return False, f"TOPOLOGY ERROR: Step {idx} depends on missing step {dep_idx}."

        # 4. 变量与 Literal 深度校验 
        clean_input = raw_input.strip().strip('"').strip("'")
        if clean_input and clean_input != "None":
            # 识别是否为变量引用 (如 v1)
            if re.match(r"^v\d+$", clean_input):
                if clean_input not in defined_vars:
                    return False, f"VARIABLE ERROR: '{clean_input}' not defined."
            # 如果包含逗号但没被识别为变量，通常是模型试图传多个变量，需警惕
            elif "," in clean_input:
                 return False, f"INPUT ERROR: Multiple variables in 'input' not supported. Use {clean_input} in a 'prompt' instead."
            elif len(clean_input) > 40:
                return False, f"LIMIT ERROR: Input at step {idx} is too long."
        
        if prompt:
            found_vars = re.findall(r"\{(\w+)\}", prompt)
            for f_var in found_vars:
                if f_var not in defined_vars:
                    return False, f"VARIABLE ERROR: Unknown '{{{f_var}}}' in prompt."

        defined_vars.add(out_var)
        parsed_steps.append({
            "idx": idx,
            "tool": tool,
            "dep": dep_list, # 现在是一个 list [1, 2] 或 None
            "input": clean_input if clean_input != "None" else None,
            "prompt": prompt,
            "out": out_var,
            "comment": comment.strip()
        })

    return True, parsed_steps

if __name__ == "__main__":
    allowed = {"get_enc", "send_mail"}
    
    # 测试 1: 合法输出
    valid_output = """
    WORKFLOW_DAG:
    1. [get_enc] -> dep: None | input: None | out: v1
    2. [try_analyze] -> dep: 1 | prompt: "Check if {v1} > 100" | out: r1
    3. [send_mail] -> dep: 2 | input: r1 | out: s1
    """
    print("Test 1 (Valid):", validate_workflow_dag(valid_output, allowed)[0])

    # 测试 2: 变量引用错误 (引用了未定义的 v2)
    invalid_output = """
    WORKFLOW_DAG:
    1. [get_enc] -> dep: None | input: None | out: v1
    2. [send_mail] -> dep: 1 | input: v2 | out: s1
    """
    success, msg = validate_workflow_dag(invalid_output, allowed)
    print("Test 2 (Var Error):", success, "| Message:", msg)