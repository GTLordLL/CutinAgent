import subprocess
import os

def grep_log_content(path: str, keyword: str, lines: int = 100):
    """
    专家级日志内容检索工具
    """
    try:
        # 1. 前置检查
        if not os.path.exists(path):
            return f"失败 | 日志文件 {path} 不存在。"
        
        if not os.path.isfile(path):
            return f"失败 | {path} 不是一个有效的文件。"

        # 2. 专家检索策略：结合 tail 和 grep
        # 逻辑：先取最后 N 行（lines），再在其中进行关键词过滤
        # 这样可以极大减少大文件的处理压力
        try:
            # 使用管道符：tail -n {lines} {path} | grep -i {keyword}
            # -i 表示忽略大小写，对小模型更友好
            # shell=True 在这里是必要的，因为涉及管道符
            cmd = f"tail -n {lines} {path} | grep -i '{keyword}' | tail -n 20"
            
            output = subprocess.check_output(cmd, shell=True, stderr=subprocess.STDOUT, universal_newlines=True)
            
            if not output.strip():
                return f"成功 | 在文件 {path} 的最近 {lines} 行中未找到关键词 '{keyword}'。"

            # 3. 结论格式化
            match_count = len(output.strip().split('\n'))
            return (
                f"成功 | 在 {path} 中检索关键词 '{keyword}'，找到 {match_count} 条匹配项（最近 {lines} 行范围）。\n"
                f"[DETAIL]\n"
                f"--- 日志片段 ---\n"
                f"{output.strip()}\n"
                f"--- 建议 ---\n"
                f"请分析上述日志中的时间戳和报错上下文。如果需要更深层的分析，请调用 ANALYSIS_BY_SUB_AGENT。"
            )

        except subprocess.CalledProcessError as e:
            # 如果 grep 没找到东西，它会返回非0码
            if e.returncode == 1:
                return f"成功 | 在 {path} 的最近 {lines} 行中未搜索到关键词 '{keyword}'。"
            return f"失败 | 执行检索时出错: {e.output}"

    except Exception as e:
        return f"失败 | 日志工具崩溃: {str(e)}"