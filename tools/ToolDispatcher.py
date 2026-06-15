from tools.git_ops.get_git_status import get_git_status
from tools.git_ops.get_git_diff import get_git_diff
from tools.git_ops.get_git_log import get_git_log
from tools.git_ops.git_commit import git_commit
from tools.git_ops.generate_commit_message import generate_commit_message
from tools.git_ops.generate_daily_report import generate_daily_report
from tools.git_ops.get_git_branches import get_git_branches
from tools.git_ops.git_delete_branch import git_delete_branch
from tools.git_ops.get_git_commits_ahead import get_git_commits_ahead
from tools.git_ops.git_push import git_push
from tools.git_ops.generate_pr_description import generate_pr_description
from tools.git_ops.generate_repo_health import generate_repo_health
from tools.git_ops.generate_release_notes import generate_release_notes
from tools.git_ops.get_git_conflicts import get_git_conflicts
from tools.git_ops.generate_conflict_resolution import generate_conflict_resolution
from tools.git_ops.create_pr import create_pr
from data_nodes.VariableStore import resolve as resolve_variable


class ToolDispatcher:
    def __init__(self):
        self.toolbox = {
            "get_git_status": get_git_status,
            "get_git_diff": get_git_diff,
            "get_git_log": get_git_log,
            "git_commit": git_commit,
            "generate_commit_message": generate_commit_message,
            "generate_daily_report": generate_daily_report,
            "get_git_branches": get_git_branches,
            "git_delete_branch": git_delete_branch,
            "get_git_commits_ahead": get_git_commits_ahead,
            "git_push": git_push,
            "generate_pr_description": generate_pr_description,
            "generate_repo_health": generate_repo_health,
            "generate_release_notes": generate_release_notes,
            "get_git_conflicts": get_git_conflicts,
            "generate_conflict_resolution": generate_conflict_resolution,
            "create_pr": create_pr,
        }

    def dispatch(self, tool_id: str, args: dict):
        if tool_id not in self.toolbox:
            return {"status": "失败", "conclusion": f"未找到工具 ID: {tool_id}", "summary": "", "detail": ""}
        try:
            resolved_args = {}
            for key, value in args.items():
                if isinstance(value, str) and value.startswith("VAR_"):
                    resolved = resolve_variable(value)
                    if not resolved:
                        return {"status": "失败", "conclusion": f"变量 {value} 未找到或已过期", "summary": "", "detail": ""}
                    resolved_args[key] = resolved
                else:
                    resolved_args[key] = value

            func = self.toolbox[tool_id]
            return func(**resolved_args)
        except TypeError as e:
            return {"status": "失败", "conclusion": f"参数错误: {str(e)}", "summary": "", "detail": ""}
        except Exception as e:
            return {"status": "失败", "conclusion": f"执行异常: {str(e)}", "summary": "", "detail": ""}
