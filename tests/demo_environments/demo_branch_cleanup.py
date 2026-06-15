"""演示 3：GIT_BRANCH_CLEANUP — 分支清理。

场景：6 个本地分支，模拟长期开发后的分支堆积。
- feature-login: 已合并，30天前 → 应清理
- bugfix-timeout: 已合并，60天前 → 应清理
- feature-cache: 未合并，5天前 → 保留
- experiment-ui: 未合并，45天前 → 保留（未合并）
- hotfix-urgent: 已合并，2天前 → 保留（14天内活跃）
"""

import os
import shutil

from tests.demo_utils import (
    C_CYAN, C_GREEN, C_RESET,
    date_days_ago, git_add_commit, git_init, run, write_file,
)


def setup_demo_branch_cleanup(repo_dir):
    """搭建演示3仓库：多分支仓库，模拟长期开发后的分支堆积。"""
    print(f"  {C_CYAN}[演示3] 搭建 GIT_BRANCH_CLEANUP 演示环境 ...{C_RESET}")

    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)

    git_init(repo_dir)
    # 确保默认分支名为 main（而非 master）
    run(["git", "branch", "-M", "main"], cwd=repo_dir)

    # -- 初始提交 (main) --
    write_file(repo_dir, "README.md", "# Demo Project\n\n一个需要清理旧分支的项目。\n")
    write_file(repo_dir, "src/main.py", 'print("Hello World")\n')
    git_add_commit(repo_dir, "init: 项目初始化")

    # -- feature-login: 已合并，30天前 --
    run(["git", "checkout", "-b", "feature-login"], cwd=repo_dir)
    write_file(repo_dir, "src/login.py", 'def login(u, p):\n    return u == "admin" and p == "123456"\n')
    git_add_commit(repo_dir, "feat(login): 实现基础登录功能",
                   date_str=date_days_ago(30))
    run(["git", "checkout", "main"], cwd=repo_dir)
    run(["git", "merge", "feature-login", "--no-edit"], cwd=repo_dir)

    # -- bugfix-timeout: 已合并，60天前 --
    run(["git", "checkout", "-b", "bugfix-timeout"], cwd=repo_dir)
    write_file(repo_dir, "src/network.py", 'TIMEOUT = 30  # 从 5 秒增加到 30 秒\n')
    git_add_commit(repo_dir, "fix(network): 修复慢速网络下的超时问题",
                   date_str=date_days_ago(60))
    run(["git", "checkout", "main"], cwd=repo_dir)
    run(["git", "merge", "bugfix-timeout", "--no-edit"], cwd=repo_dir)

    # -- feature-cache: 未合并，5天前 -- 不应该被清理
    run(["git", "checkout", "-b", "feature-cache"], cwd=repo_dir)
    write_file(repo_dir, "src/cache.py", 'cache = {}\ndef get(k): return cache.get(k)\ndef set(k, v): cache[k] = v\n')
    git_add_commit(repo_dir, "feat(cache): 实现内存缓存层（WIP）",
                   date_str=date_days_ago(5))
    # 不在 main 上 merge 这个分支

    # -- experiment-ui: 未合并，45天前 -- 不应该被清理（未合并）
    run(["git", "checkout", "main"], cwd=repo_dir)
    run(["git", "checkout", "-b", "experiment-ui"], cwd=repo_dir)
    write_file(repo_dir, "src/ui_prototype.py", '# Experimental UI\nprint("TODO: rewrite in React")\n')
    git_add_commit(repo_dir, "experiment: UI 原型探索（未完成）",
                   date_str=date_days_ago(45))
    # 不 merge

    # -- hotfix-urgent: 已合并，2天前 -- 不应该被清理（14天内活跃）
    run(["git", "checkout", "main"], cwd=repo_dir)
    run(["git", "checkout", "-b", "hotfix-urgent"], cwd=repo_dir)
    write_file(repo_dir, "src/config.py", 'DEBUG = False  # 关闭调试模式\n')
    git_add_commit(repo_dir, "hotfix(config): 紧急关闭生产环境调试模式",
                   date_str=date_days_ago(2))
    run(["git", "checkout", "main"], cwd=repo_dir)
    run(["git", "merge", "hotfix-urgent", "--no-edit"], cwd=repo_dir)

    # -- 最后在 main 上做一次提交，让 main 保持最新 --
    write_file(repo_dir, "src/utils.py", '# 工具函数\n')
    git_add_commit(repo_dir, "chore: 添加工具模块占位")

    # 回到 main
    run(["git", "checkout", "main"], cwd=repo_dir)

    print(f"         {C_GREEN}分支就绪{C_RESET}: 6 个本地分支")
    print(f"           main (HEAD)         — 当前分支")
    print(f"           feature-login        — 已合并，30天前 → 应清理")
    print(f"           bugfix-timeout       — 已合并，60天前 → 应清理")
    print(f"           feature-cache        — 未合并，5天前  → 保留")
    print(f"           experiment-ui        — 未合并，45天前 → 保留")
    print(f"           hotfix-urgent        — 已合并，2天前  → 保留 (14天内活跃)")
