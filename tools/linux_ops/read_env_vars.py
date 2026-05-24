import os

def read_env_vars(filter_key: str = ""):
    """
    专家级环境变量检索工具
    """
    try:
        # 1. 获取所有环境变量
        all_envs = os.environ.copy()
        
        # 2. 过滤逻辑
        if filter_key:
            # 采用不区分大小写的模糊匹配，提高容错率
            filtered_envs = {
                k: v for k, v in all_envs.items() 
                if filter_key.lower() in k.lower() or filter_key.lower() in v.lower()
            }
            target_desc = f"包含关键词 '{filter_key}' 的"
        else:
            # 无过滤条件 → 返回核心环境变量（避免全量输出导致 Token 爆炸）
            important_keys = ["PATH", "USER", "SHELL", "LANG", "HOME", "PWD"]
            filtered_envs = {k: all_envs[k] for k in important_keys if k in all_envs}
            target_desc = "核心关键"

        # 3. 专家结论生成
        if not filtered_envs:
            return f"成功 | 未找到任何{target_desc}环境变量。请检查配置是否已正确导出（export）。"

        # 格式化输出清单
        env_list = [f"{k}={v}" for k, v in filtered_envs.items()]
        
        # 特殊专家逻辑：如果是在排查 PATH
        path_advice = ""
        if filter_key.upper() == "PATH" and "PATH" in filtered_envs:
            path_advice = "\n结论：PATH 变量已读取。如果命令找不到，请确认可执行文件是否在上述目录中。"

        return (
            f"成功 | [环境配置检查] 已获取 {len(env_list)} 条{target_desc}变量{path_advice}\n"
            f"[DETAIL]\n"
            + "\n".join(env_list)
        )

    except Exception as e:
        return f"失败 | 读取环境变量时出错: {str(e)}"