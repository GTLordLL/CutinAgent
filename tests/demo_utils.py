"""Git SOP 演示环境 — 共享工具函数与常量。"""

import os
import shutil
import subprocess
from datetime import datetime, timedelta

# ---------- 路径常量 ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TMP_DIR = os.path.join(PROJECT_ROOT, "tmp")
DEMO1_DIR = os.path.join(TMP_DIR, "demo_smart_commit")
DEMO2_DIR = os.path.join(TMP_DIR, "demo_branch_cleanup")

DEMO_DIRS = [DEMO1_DIR, DEMO2_DIR]

# ---------- ANSI 颜色 ----------
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_CYAN = "\033[36m"
C_MAGENTA = "\033[35m"
C_RESET = "\033[0m"


def run(cmd, cwd=None, env=None, check=True):
    """执行 shell 命令，返回 CompletedProcess。"""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd, cwd=cwd, env=merged_env,
        capture_output=True, text=True, check=check,
    )


def git_init(repo_dir):
    """初始化 git 仓库并配置用户信息。"""
    os.makedirs(repo_dir, exist_ok=True)
    run(["git", "init"], cwd=repo_dir)
    run(["git", "config", "user.name", "张三"], cwd=repo_dir)
    run(["git", "config", "user.email", "zhangsan@example.com"], cwd=repo_dir)


def write_file(repo_dir, path, content):
    """在仓库中写入文件，自动创建父目录。"""
    full = os.path.join(repo_dir, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def git_add_commit(repo_dir, message, date_str=None):
    """git add -A + git commit，可选指定提交日期。"""
    env = {}
    if date_str:
        env["GIT_COMMITTER_DATE"] = date_str
        env["GIT_AUTHOR_DATE"] = date_str
    run(["git", "add", "-A"], cwd=repo_dir)
    run(["git", "commit", "-m", message], cwd=repo_dir, env=env if env else None)


def date_days_ago(n_days: int) -> str:
    """返回 N 天前的日期字符串 (YYYY-MM-DD)。"""
    dt = datetime.now() - timedelta(days=n_days)
    return dt.strftime("%Y-%m-%d") + "T10:00:00"
