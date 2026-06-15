"""演示 6：GIT_CONFLICT_RESOLVE — 冲突解决辅助。

场景：两个分支修改了同一文件的不同功能，合并时产生 2 个冲突文件。
- main: 添加了任务验证逻辑 + 修改 MAX_RETRIES=10
- feature-priority: 添加了优先级排序逻辑 + 修改 MAX_RETRIES=5
- 合并 feature-priority → main 时在 process_task() 和 config.py 各产生 1 个冲突

仓库在 setup 后处于 未解决冲突 状态，可直接测试 get_git_conflicts。
"""

import os
import shutil

from tests.demo_utils import (
    C_CYAN, C_GREEN, C_RESET, C_YELLOW,
    date_days_ago, git_add_commit, git_init, run, write_file,
)


def setup_demo_conflict_resolve(repo_dir):
    """搭建演示6仓库：合并冲突状态，2个冲突文件待解决。"""
    print(f"  {C_CYAN}[演示6] 搭建 GIT_CONFLICT_RESOLVE 演示环境 ...{C_RESET}")

    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)

    git_init(repo_dir)
    run(["git", "branch", "-M", "main"], cwd=repo_dir)

    # ====== 初始提交 (main) — 项目骨架 ======
    write_file(repo_dir, "README.md", '''\
# TaskManager — 任务管理器

一个简单的命令行任务管理工具，支持优先级排序和任务验证。
''')

    write_file(repo_dir, "src/__init__.py", "")

    write_file(repo_dir, "src/config.py", '''\
"""任务管理器配置。"""

# 默认任务优先级（0=普通，数字越大优先级越高）
DEFAULT_PRIORITY = 0

# 处理失败最大重试次数
MAX_RETRIES = 3

# 任务标题最大长度
MAX_TITLE_LENGTH = 100
''')

    write_file(repo_dir, "src/task.py", '''\
"""任务管理核心模块。"""


class Task:
    def __init__(self, title: str, description: str = "", priority: int = 0):
        self.title = title
        self.description = description
        self.priority = priority


class TaskManager:
    def __init__(self):
        self._tasks: list[Task] = []
        self._completed: list[Task] = []

    def add_task(self, task: Task):
        self._tasks.append(task)

    def process_task(self):
        if not self._tasks:
            return None
        task = self._tasks.pop(0)
        print(f"Processing: {task.title}")
        self._completed.append(task)
        return task

    def list_tasks(self) -> list[str]:
        return [t.title for t in self._tasks]

    def list_completed(self) -> list[str]:
        return [t.title for t in self._completed]
''')

    write_file(repo_dir, "src/cli.py", '''\
"""命令行接口。"""
from src.task import Task, TaskManager


def main():
    mgr = TaskManager()
    mgr.add_task(Task("示例任务", "这是一个演示任务"))
    mgr.process_task()
    print("任务列表:", mgr.list_tasks())


if __name__ == "__main__":
    main()
''')

    git_add_commit(repo_dir, "init: 初始化任务管理器项目骨架",
                   date_str=date_days_ago(14))

    # ====== feature-priority 分支 — 添加优先级排序 + 修改MAX_RETRIES=5 ======
    run(["git", "checkout", "-b", "feature-priority"], cwd=repo_dir)

    # 修改 process_task()：添加优先级排序
    write_file(repo_dir, "src/task.py", '''\
"""任务管理核心模块（优先级增强）。"""


class Task:
    def __init__(self, title: str, description: str = "", priority: int = 0):
        self.title = title
        self.description = description
        self.priority = priority


class TaskManager:
    def __init__(self):
        self._tasks: list[Task] = []
        self._completed: list[Task] = []

    def add_task(self, task: Task):
        self._tasks.append(task)

    def process_task(self):
        if not self._tasks:
            return None
        # 按优先级降序排列（高优先级先处理）
        self._tasks.sort(key=lambda t: t.priority, reverse=True)
        task = self._tasks.pop(0)
        print(f"[P{task.priority}] Processing: {task.title}")
        self._completed.append(task)
        return task

    def list_tasks(self) -> list[str]:
        return [t.title for t in self._tasks]

    def list_completed(self) -> list[str]:
        return [t.title for t in self._completed]
''')

    # 修改 config.py：MAX_RETRIES 5
    write_file(repo_dir, "src/config.py", '''\
"""任务管理器配置（优先级分支）。"""

# 默认任务优先级（0=普通，数字越大优先级越高）
DEFAULT_PRIORITY = 0

# 处理失败最大重试次数（优先级队列场景需要更多重试）
MAX_RETRIES = 5

# 任务标题最大长度
MAX_TITLE_LENGTH = 100
''')

    git_add_commit(repo_dir,
                   "feat(priority): 添加任务优先级排序，高优先级任务优先处理",
                   date_str=date_days_ago(7))

    # ====== main 分支继续演进（与 feature-priority 分叉）— 添加验证 + 修改MAX_RETRIES=10 ======
    run(["git", "checkout", "main"], cwd=repo_dir)

    # 修改 process_task()：添加标题验证（与 feature-priority 的排序逻辑冲突）
    write_file(repo_dir, "src/task.py", '''\
"""任务管理核心模块（验证增强）。"""


class Task:
    def __init__(self, title: str, description: str = "", priority: int = 0):
        self.title = title
        self.description = description
        self.priority = priority


class TaskManager:
    def __init__(self):
        self._tasks: list[Task] = []
        self._completed: list[Task] = []

    def add_task(self, task: Task):
        self._tasks.append(task)

    def process_task(self):
        if not self._tasks:
            return None
        task = self._tasks.pop(0)
        # 验证任务数据完整性
        if not task.title or not task.title.strip():
            print("Skipping task with empty title")
            return None
        if len(task.title) > 100:
            print(f"Task title too long ({len(task.title)} chars), truncating")
            task.title = task.title[:100]
        print(f"Processing: {task.title}")
        self._completed.append(task)
        return task

    def list_tasks(self) -> list[str]:
        return [t.title for t in self._tasks]

    def list_completed(self) -> list[str]:
        return [t.title for t in self._completed]
''')

    # 修改 config.py：MAX_RETRIES 10（与 feature-priority 的 5 冲突）
    write_file(repo_dir, "src/config.py", '''\
"""任务管理器配置（验证增强版）。"""

# 默认任务优先级（0=普通，数字越大优先级越高）
DEFAULT_PRIORITY = 0

# 处理失败最大重试次数（增加重试以提高可靠性）
MAX_RETRIES = 10

# 任务标题最大长度
MAX_TITLE_LENGTH = 100
''')

    git_add_commit(repo_dir,
                   "feat(validate): 添加任务标题验证，防止空标题和超长标题",
                   date_str=date_days_ago(3))

    # 在 main 上再做一个无关提交，让历史更真实
    write_file(repo_dir, "src/utils.py", '''\
"""工具函数。"""
import re


def sanitize_title(title: str) -> str:
    """去除标题中的危险字符。"""
    return re.sub(r'[<>"|]', '', title).strip()
''')
    git_add_commit(repo_dir, "chore: 添加字符串清理工具函数",
                   date_str=date_days_ago(1))

    # ====== 合并 feature-priority → main，触发冲突！ ======
    # 使用 --no-edit 避免打开编辑器，check=False 因为 merge 会因冲突返回非零
    result = run(
        ["git", "merge", "feature-priority", "--no-edit"],
        cwd=repo_dir, check=False
    )
    # merge 预期失败（有冲突），输出合并状态
    if result.returncode != 0:
        # 获取冲突文件列表确认
        conflict_check = run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            cwd=repo_dir, check=False
        )
        conflicted = [f.strip() for f in conflict_check.stdout.strip().split('\n') if f.strip()]
        print(f"         {C_YELLOW}合并冲突已触发{C_RESET}: {len(conflicted)} 个文件冲突")
        for cf in conflicted:
            print(f"           ⚠ {cf}")
    else:
        print(f"         {C_YELLOW}意外：合并自动成功（未产生冲突）{C_RESET}")

    print(f"         {C_GREEN}仓库就绪{C_RESET}: 2 个冲突文件待解决")
    print(f"           src/task.py   — process_task() 方法（排序 vs 验证）")
    print(f"           src/config.py — MAX_RETRIES (5 vs 10)")
    print(f"           用法: get_git_conflicts() 查看冲突内容")
    print(f"           回滚: git merge --abort 可撤销本次合并")
