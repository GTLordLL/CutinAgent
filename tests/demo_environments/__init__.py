"""Git SOP 演示环境 — 各 demo setup 函数。"""

from tests.demo_environments.demo_smart_commit import setup_demo_smart_commit
from tests.demo_environments.demo_branch_cleanup import setup_demo_branch_cleanup

__all__ = [
    "setup_demo_smart_commit",
    "setup_demo_branch_cleanup",
]
