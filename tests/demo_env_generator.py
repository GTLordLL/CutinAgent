#!/usr/bin/env python3
"""Git SOP 演示环境生成器。

在 tmp/ 下生成逼真的 Git 演示仓库，用于录制 Git SOP 的视频演示。
可随时生成和删除。

用法:
    python tests/demo_env_generator.py --setup          # 生成全部演示环境
    python tests/demo_env_generator.py --setup --demo 1  # 仅生成演示1
    python tests/demo_env_generator.py --setup --demo 2  # 仅生成演示2
    python tests/demo_env_generator.py --setup --demo 3  # 仅生成演示3 (GIT_BRANCH_CLEANUP)
    python tests/demo_env_generator.py --setup --demo 4  # 仅生成演示4 (GIT_REPO_HEALTH)
    python tests/demo_env_generator.py --show            # 展示环境状态 + 演示脚本
    python tests/demo_env_generator.py --clean           # 删除所有演示环境
"""

import argparse
import os
import shutil
import sys

# 确保项目根目录在 sys.path 中，支持 python tests/demo_env_generator.py 方式运行
_PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from tests.demo_environments import (
    setup_demo_branch_cleanup,
    setup_demo_conflict_resolve,
    setup_demo_daily_summary,
    setup_demo_release_notes,
    setup_demo_repo_health,
    setup_demo_smart_commit,
)
from tests.demo_utils import (
    C_BOLD, C_CYAN, C_GREEN, C_MAGENTA, C_RESET, C_YELLOW,
    DEMO1_DIR, DEMO2_DIR, DEMO3_DIR, DEMO4_DIR, DEMO5_DIR, DEMO6_DIR, DEMO_DIRS,
    TMP_DIR, run,
)

# ---------- setup 分发 ----------

SETUP_FUNCTIONS = {
    1: (DEMO1_DIR, setup_demo_smart_commit),
    2: (DEMO2_DIR, setup_demo_daily_summary),
    3: (DEMO3_DIR, setup_demo_branch_cleanup),
    4: (DEMO4_DIR, setup_demo_repo_health),
    5: (DEMO5_DIR, setup_demo_release_notes),
    6: (DEMO6_DIR, setup_demo_conflict_resolve),
}


# ---------- show ----------

def _show_demo1():
    """展示演示1状态和脚本。"""
    has_it = os.path.isdir(os.path.join(DEMO1_DIR, ".git"))
    status = f"{C_GREEN}✓ 就绪{C_RESET}" if has_it else f"{C_YELLOW}✗ 未生成{C_RESET}"
    print(f"  {C_BOLD}演示 1: GIT_SMART_COMMIT{C_RESET}  [{status}]")
    print(f"  路径: {DEMO1_DIR}")
    if has_it:
        r = run(["git", "status", "--porcelain"], cwd=DEMO1_DIR, check=False)
        lines = r.stdout.strip().split("\n") if r.stdout.strip() else []
        mods = sum(1 for l in lines if l and (l[1] == "M" or (len(l) > 2 and l[:2] == " M")))
        adds = sum(1 for l in lines if l and l.startswith("??"))
        dels = sum(1 for l in lines if l and (" D" in l[:3] or l.startswith("D ")))
        print(f"  变更: {C_YELLOW}修改×{mods}{C_RESET}  {C_GREEN}新增×{adds}{C_RESET}  {C_MAGENTA}删除×{dels}{C_RESET}")
    return has_it


def _show_demo2():
    """展示演示2状态和脚本。"""
    has_it = os.path.isdir(os.path.join(DEMO2_DIR, ".git"))
    status = f"{C_GREEN}✓ 就绪{C_RESET}" if has_it else f"{C_YELLOW}✗ 未生成{C_RESET}"
    print(f"\n  {C_BOLD}演示 2: GIT_DAILY_SUMMARY{C_RESET}  [{status}]")
    print(f"  路径: {DEMO2_DIR}")
    if has_it:
        r = run(["git", "log", "--since=midnight", "--oneline"], cwd=DEMO2_DIR, check=False)
        count = len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
        print(f"  今日提交: {C_GREEN}{count} 条{C_RESET}")
    return has_it


def _show_demo3():
    """展示演示3状态和脚本。"""
    has_it = os.path.isdir(os.path.join(DEMO3_DIR, ".git"))
    status = f"{C_GREEN}✓ 就绪{C_RESET}" if has_it else f"{C_YELLOW}✗ 未生成{C_RESET}"
    print(f"\n  {C_BOLD}演示 3: GIT_BRANCH_CLEANUP{C_RESET}  [{status}]")
    print(f"  路径: {DEMO3_DIR}")
    if has_it:
        r = run(["git", "branch", "-a"], cwd=DEMO3_DIR, check=False)
        branches = [b.strip().lstrip("* ") for b in r.stdout.strip().split("\n") if b.strip()]
        print(f"  分支数: {C_GREEN}{len(branches)} 个{C_RESET}")
        r2 = run(["git", "branch", "--merged"], cwd=DEMO3_DIR, check=False)
        merged = [b.strip().lstrip("* ") for b in r2.stdout.strip().split("\n") if b.strip()]
        print(f"  已合并: {len(merged)} 个 (可清理)")
    return has_it


def _show_demo4():
    """展示演示4状态和脚本。"""
    has_it = os.path.isdir(os.path.join(DEMO4_DIR, ".git"))
    status = f"{C_GREEN}✓ 就绪{C_RESET}" if has_it else f"{C_YELLOW}✗ 未生成{C_RESET}"
    print(f"\n  {C_BOLD}演示 4: GIT_REPO_HEALTH{C_RESET}  [{status}]")
    print(f"  路径: {DEMO4_DIR}")
    if has_it:
        r = run(["git", "branch", "-a"], cwd=DEMO4_DIR, check=False)
        branches = [b.strip().lstrip("* ") for b in r.stdout.strip().split("\n") if b.strip()]
        print(f"  分支数: {C_GREEN}{len(branches)} 个{C_RESET}")
        r2 = run(["git", "branch", "--merged"], cwd=DEMO4_DIR, check=False)
        merged = [b.strip().lstrip("* ") for b in r2.stdout.strip().split("\n") if b.strip()]
        print(f"  已合并: {len(merged)} 个 (可清理)")
        r3 = run(["git", "status", "--porcelain"], cwd=DEMO4_DIR, check=False)
        lines = [l for l in r3.stdout.strip().split("\n") if l.strip()] if r3.stdout.strip() else []
        staged = sum(1 for l in lines if l[0] != " " and l[1] != "?")
        modified = sum(1 for l in lines if l[0] != "M" and l[1] == "M")
        untracked = sum(1 for l in lines if l.startswith("??"))
        r5 = run(["git", "log", "--since=7.days.ago", "--oneline"], cwd=DEMO4_DIR, check=False)
        log_count = len([l for l in r5.stdout.strip().split("\n") if l.strip()]) if r5.stdout.strip() else 0
        print(f"  工作区: 已暂存×{staged} 已修改×{modified} 未跟踪×{untracked}")
        print(f"  近7天提交: {C_GREEN}{log_count} 条{C_RESET}")
    return has_it


def _show_demo5():
    """展示演示5状态和脚本。"""
    has_it = os.path.isdir(os.path.join(DEMO5_DIR, ".git"))
    status = f"{C_GREEN}✓ 就绪{C_RESET}" if has_it else f"{C_YELLOW}✗ 未生成{C_RESET}"
    print(f"\n  {C_BOLD}演示 5: GIT_RELEASE_NOTES{C_RESET}  [{status}]")
    print(f"  路径: {DEMO5_DIR}")
    if has_it:
        r = run(["git", "tag", "-l"], cwd=DEMO5_DIR, check=False)
        tags = [t.strip() for t in r.stdout.strip().split("\n") if t.strip()]
        print(f"  版本 Tag: {C_GREEN}{', '.join(tags)}{C_RESET}")
        r2 = run(["git", "log", "--oneline"], cwd=DEMO5_DIR, check=False)
        lines = [l for l in r2.stdout.strip().split("\n") if l.strip()]
        print(f"  总提交数: {C_GREEN}{len(lines)} 条{C_RESET}")
        r3 = run(["git", "log", "--oneline", "v0.1.0..v0.2.0"], cwd=DEMO5_DIR, check=False)
        between = [l for l in r3.stdout.strip().split("\n") if l.strip()]
        print(f"  v0.1.0→v0.2.0: {C_CYAN}{len(between)} 条提交{C_RESET}")
    return has_it


def _show_demo6():
    """展示演示6状态和脚本。"""
    has_it = os.path.isdir(os.path.join(DEMO6_DIR, ".git"))
    status = f"{C_GREEN}✓ 就绪{C_RESET}" if has_it else f"{C_YELLOW}✗ 未生成{C_RESET}"
    print(f"\n  {C_BOLD}演示 6: GIT_CONFLICT_RESOLVE{C_RESET}  [{status}]")
    print(f"  路径: {DEMO6_DIR}")
    if has_it:
        r = run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=DEMO6_DIR, check=False)
        conflicts = [c.strip() for c in r.stdout.strip().split("\n") if c.strip()]
        print(f"  冲突文件: {C_YELLOW}{len(conflicts)} 个{C_RESET}")
        for cf in conflicts:
            print(f"    ⚠ {cf}")
        # 检查 merge 状态
        merge_head_exists = os.path.exists(os.path.join(DEMO6_DIR, ".git", "MERGE_HEAD"))
        rebase_exists = os.path.exists(os.path.join(DEMO6_DIR, ".git", "rebase-merge"))
        if merge_head_exists:
            print(f"  状态: 合并进行中 (git merge --abort 可回滚)")
        elif rebase_exists:
            print(f"  状态: 变基进行中 (git rebase --abort 可回滚)")
    return has_it


def _print_demo_scripts(has1, has2, has3, has4, has5, has6):
    """打印演示录制脚本。"""
    print(f"\n{C_BOLD}{'='*60}{C_RESET}")
    print(f"{C_BOLD}  📋 录制演示脚本{C_RESET}")
    print(f"{C_BOLD}{'='*60}{C_RESET}")

    scripts = []
    if has1:
        scripts.append(f"""
{C_CYAN}{'─'*60}{C_RESET}
{C_BOLD} 演示 1 — GIT_SMART_COMMIT（智能提交）{C_RESET}
{C_CYAN}{'─'*60}{C_RESET}

# 步骤 1：展示混乱的工作区
{C_YELLOW}cd {DEMO1_DIR}{C_RESET}
{C_YELLOW}git status{C_RESET}
{C_YELLOW}git diff --stat{C_RESET}

# 步骤 2：启动 Agent
{C_YELLOW}cutin{C_RESET}

# 步骤 3：输入指令
> {C_GREEN}帮我分析当前改动，生成一个规范的 commit message 并提交{C_RESET}

# 步骤 4：验证
{C_YELLOW}git log -1 --format="%h %s%n%b"{C_RESET}
""")
    if has2:
        scripts.append(f"""
{C_CYAN}{'─'*60}{C_RESET}
{C_BOLD} 演示 2 — GIT_DAILY_SUMMARY（每日汇总）{C_RESET}
{C_CYAN}{'─'*60}{C_RESET}

{C_YELLOW}cd {DEMO2_DIR}{C_RESET}
{C_YELLOW}git log --since=midnight --oneline{C_RESET}
{C_YELLOW}cutin{C_RESET}
> {C_GREEN}生成今天的开发工作总结{C_RESET}
""")
    if has3:
        scripts.append(f"""
{C_CYAN}{'─'*60}{C_RESET}
{C_BOLD} 演示 3 — GIT_BRANCH_CLEANUP（分支清理）{C_RESET}
{C_CYAN}{'─'*60}{C_RESET}

# 步骤 1：展示分支堆积
{C_YELLOW}cd {DEMO3_DIR}{C_RESET}
{C_YELLOW}git branch -a{C_RESET}

# 步骤 2：Headless 模式直接执行
{C_YELLOW}cutin run --sop GIT_BRANCH_CLEANUP --output json "清理分支"{C_RESET}

# 步骤 3：验证分支已清理
{C_YELLOW}git branch -a{C_RESET}
""")
    if has4:
        scripts.append(f"""
{C_CYAN}{'─'*60}{C_RESET}
{C_BOLD} 演示 4 — GIT_REPO_HEALTH（仓库健康检查）{C_RESET}
{C_CYAN}{'─'*60}{C_RESET}

# 步骤 1：展示仓库状态
{C_YELLOW}cd {DEMO4_DIR}{C_RESET}
{C_YELLOW}git status{C_RESET}
{C_YELLOW}git branch -a{C_RESET}
{C_YELLOW}git log --since=7.days.ago --oneline{C_RESET}

# 步骤 2：Headless 模式执行健康检查
{C_YELLOW}cutin run --sop GIT_REPO_HEALTH --output json "检查仓库健康状态"{C_RESET}
""")
    if has5:
        scripts.append(f"""
{C_CYAN}{'─'*60}{C_RESET}
{C_BOLD} 演示 5 — GIT_RELEASE_NOTES（Release Notes 生成）{C_RESET}
{C_CYAN}{'─'*60}{C_RESET}

# 步骤 1：展示 tag 和提交范围
{C_YELLOW}cd {DEMO5_DIR}{C_RESET}
{C_YELLOW}git tag -l{C_RESET}
{C_YELLOW}git log --oneline v0.1.0..v0.2.0{C_RESET}

# 步骤 2：Headless 模式执行 Release Notes 生成
{C_YELLOW}cutin run --sop GIT_RELEASE_NOTES --output json "生成 v0.1.0 到 v0.2.0 的 Release Notes"{C_RESET}
""")
    if has6:
        scripts.append(f"""
{C_CYAN}{'─'*60}{C_RESET}
{C_BOLD} 演示 6 — GIT_CONFLICT_RESOLVE（冲突解决辅助）{C_RESET}
{C_CYAN}{'─'*60}{C_RESET}

# 步骤 1：展示冲突状态
{C_YELLOW}cd {DEMO6_DIR}{C_RESET}
{C_YELLOW}git status{C_RESET}
{C_YELLOW}git diff --name-only --diff-filter=U{C_RESET}

# 步骤 2：Headless 模式执行冲突分析
{C_YELLOW}cutin run --sop GIT_CONFLICT_RESOLVE --output json "帮我分析解决合并冲突"{C_RESET}

# 步骤 3（可选）：放弃本次合并
{C_YELLOW}git merge --abort{C_RESET}
""")
    for s in scripts:
        print(s)


def show_demo_status():
    """展示演示环境状态和录制脚本。"""
    print(f"\n{C_BOLD}{'='*60}{C_RESET}")
    print(f"{C_BOLD}  Git SOP 演示环境状态{C_RESET}")
    print(f"{C_BOLD}{'='*60}{C_RESET}\n")

    has1 = _show_demo1()
    has2 = _show_demo2()
    has3 = _show_demo3()
    has4 = _show_demo4()
    has5 = _show_demo5()
    has6 = _show_demo6()

    if has1 or has2 or has3 or has4 or has5 or has6:
        _print_demo_scripts(has1, has2, has3, has4, has5, has6)

    if not has1 and not has2 and not has3 and not has4 and not has5 and not has6:
        print(f"\n  {C_YELLOW}环境未生成，请先运行:{C_RESET}")
        print(f"  python tests/demo_env_generator.py --setup\n")
    else:
        print(f"{C_BOLD}{'='*60}{C_RESET}")
        print(f"  清理环境: {C_YELLOW}python tests/demo_env_generator.py --clean{C_RESET}")
        print(f"{C_BOLD}{'='*60}{C_RESET}\n")


# ---------- clean ----------

def clean_demo_envs():
    """删除所有演示环境。"""
    print(f"  {C_YELLOW}清理演示环境 ...{C_RESET}")
    for d in DEMO_DIRS:
        if os.path.isdir(d):
            shutil.rmtree(d)
            print(f"    已删除: {d}")
    if os.path.isdir(TMP_DIR) and not os.listdir(TMP_DIR):
        os.rmdir(TMP_DIR)
        print(f"    已删除空目录: {TMP_DIR}")
    print(f"  {C_GREEN}清理完成{C_RESET}")


# ---------- CLI ----------

def main():
    parser = argparse.ArgumentParser(
        description="Git SOP 演示环境生成器 — 在 tmp/ 下生成可随时清理的演示用 Git 仓库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --setup              生成全部演示环境
  %(prog)s --setup --demo 1     仅生成 GIT_SMART_COMMIT 演示
  %(prog)s --setup --demo 2     仅生成 GIT_DAILY_SUMMARY 演示
  %(prog)s --setup --demo 3     仅生成 GIT_BRANCH_CLEANUP 演示
  %(prog)s --setup --demo 4     仅生成 GIT_REPO_HEALTH 演示
  %(prog)s --setup --demo 5     仅生成 GIT_RELEASE_NOTES 演示
  %(prog)s --setup --demo 6     仅生成 GIT_CONFLICT_RESOLVE 演示
  %(prog)s --show               查看状态 + 演示脚本
  %(prog)s --clean              删除所有演示环境
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--setup", action="store_true", help="生成演示环境")
    group.add_argument("--show", action="store_true", help="展示环境状态与演示脚本")
    group.add_argument("--clean", action="store_true", help="删除所有演示环境")
    parser.add_argument("--demo", type=int, choices=[1, 2, 3, 4, 5, 6], default=0,
                        help="指定演示编号 (1/2/3/4/5/6)，不指定则生成全部")

    args = parser.parse_args()

    if args.show:
        show_demo_status()
        return

    if args.clean:
        clean_demo_envs()
        return

    if args.setup:
        print(f"\n{C_BOLD}{'='*60}{C_RESET}")
        print(f"{C_BOLD}  Git SOP 演示环境生成{C_RESET}")
        print(f"{C_BOLD}{'='*60}{C_RESET}\n")

        do_all = args.demo == 0

        for num in (1, 2, 3, 4, 5, 6):
            if do_all or args.demo == num:
                demo_dir, setup_fn = SETUP_FUNCTIONS[num]
                setup_fn(demo_dir)
                print()

        print(f"{C_BOLD}{'='*60}{C_RESET}")
        print(f"  {C_GREEN}演示环境生成完毕！{C_RESET}")
        print(f"  查看演示脚本: python tests/demo_env_generator.py --show")
        print(f"  清理环境:     python tests/demo_env_generator.py --clean")
        print(f"{C_BOLD}{'='*60}{C_RESET}\n")


if __name__ == "__main__":
    main()
