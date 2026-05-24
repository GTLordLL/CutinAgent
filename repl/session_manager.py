import os as _os
from datetime import datetime


def create_session_dir(base_dir: str = "history") -> str:
    """创建会话目录并返回路径。"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    path = f"{base_dir}/{timestamp}_repl_session"
    _os.makedirs(path, exist_ok=True)
    return path


def write_run_summary(session_dir: str, user_query: str,
                      start_dt: datetime, end_dt: datetime, elapsed: float,
                      node_timings: list, final_task_status: str,
                      total_rounds: int):
    """在会话目录写入 RUN_SUMMARY.txt。"""
    path = f"{session_dir}/RUN_SUMMARY.txt"
    with open(path, "w", encoding="utf-8") as f:
        f.write(f"{'=' * 60}\n")
        f.write(f"CutinAgent REPL 运行摘要\n")
        f.write(f"{'=' * 60}\n\n")
        f.write(f"用户指令: {user_query}\n")
        f.write(f"会话目录: {session_dir}\n")
        f.write(f"开始时间: {start_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"结束时间: {end_dt.strftime('%Y-%m-%d %H:%M:%S')}\n")
        f.write(f"总耗时: {elapsed:.2f}s\n\n")

        f.write("--- 节点耗时分布 ---\n")
        for node_name, dur in node_timings:
            f.write(f"  {node_name}: {dur:.2f}s\n")

        f.write(f"\n--- 最终状态 ---\n")
        f.write(f"  task_status: {final_task_status}\n")
        f.write(f"  总轮次: {total_rounds}\n")
