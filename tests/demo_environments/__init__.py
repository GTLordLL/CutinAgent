"""Git SOP 演示环境 — 各 demo setup 函数。"""

from tests.demo_environments.demo_smart_commit import setup_demo_smart_commit
from tests.demo_environments.demo_daily_summary import setup_demo_daily_summary
from tests.demo_environments.demo_branch_cleanup import setup_demo_branch_cleanup
from tests.demo_environments.demo_repo_health import setup_demo_repo_health
from tests.demo_environments.demo_release_notes import setup_demo_release_notes
from tests.demo_environments.demo_conflict_resolve import setup_demo_conflict_resolve

__all__ = [
    "setup_demo_smart_commit",
    "setup_demo_daily_summary",
    "setup_demo_branch_cleanup",
    "setup_demo_repo_health",
    "setup_demo_release_notes",
    "setup_demo_conflict_resolve",
]
