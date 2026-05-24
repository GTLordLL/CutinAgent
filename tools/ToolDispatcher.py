from tools.git_ops.get_git_status import get_git_status
from tools.git_ops.get_git_diff import get_git_diff
from tools.git_ops.get_git_log import get_git_log
from tools.git_ops.git_commit import git_commit
from tools.git_ops.generate_commit_message import generate_commit_message
from tools.git_ops.generate_daily_report import generate_daily_report
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
