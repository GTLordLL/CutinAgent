import json
import inspect
import os as _os

from tools.git_ops.get_git_status import get_git_status
from tools.git_ops.get_git_diff import get_git_diff
from tools.git_ops.get_git_log import get_git_log
from tools.git_ops.git_commit import git_commit
from tools.git_ops.generate_commit_message import generate_commit_message
from tools.git_ops.get_git_branches import get_git_branches
from tools.git_ops.git_delete_branch import git_delete_branch
from tools.git_ops.get_git_commits_ahead import get_git_commits_ahead
from tools.git_ops.git_push import git_push
from tools.git_ops.generate_pr_description import generate_pr_description
from tools.git_ops.get_git_conflicts import get_git_conflicts
from tools.git_ops.create_pr import create_pr
from tools.linux_ops.get_system_health import get_system_health
from tools.linux_ops.list_top_processes import list_top_processes
from tools.linux_ops.run_command import run_command
from tools.linux_ops.check_file_access import check_file_access
from data_nodes.VariableStore import resolve as resolve_variable


class ToolDispatcher:
    def __init__(self, tools_df=None, sops_df=None, composite_executor=None):
        # ── 函数映射表（tool_id → callable，仅 atomic 工具）──
        self._func_map = {
            "get_git_status": get_git_status,
            "get_git_diff": get_git_diff,
            "get_git_log": get_git_log,
            "git_commit": git_commit,
            "generate_commit_message": generate_commit_message,
            "get_git_branches": get_git_branches,
            "git_delete_branch": git_delete_branch,
            "get_git_commits_ahead": get_git_commits_ahead,
            "git_push": git_push,
            "generate_pr_description": generate_pr_description,
            "get_git_conflicts": get_git_conflicts,
            "create_pr": create_pr,
            "get_system_health": get_system_health,
            "list_top_processes": list_top_processes,
            "run_command": run_command,
            "check_file_access": check_file_access,
        }

        # ── 加载 tools_df（None 时回退加载 CSV，向后兼容零参构造）──
        if tools_df is None:
            from utils.load_csv import load_csv_df
            tools_df = load_csv_df("tools/tools.csv")
            if tools_df is None:
                import pandas as pd
                tools_df = pd.DataFrame(columns=[
                    "Tool_ID", "Keywords", "Tool_Type",
                    "Func_Desc", "Args_Schema", "param_desc",
                ])

        # ── 加载 sops_df（None 时回退加载 CSV）──
        if sops_df is None:
            from utils.load_csv import load_csv_df
            sops_df = load_csv_df("sop/sops.csv")
            if sops_df is None:
                import pandas as pd
                sops_df = pd.DataFrame(columns=[
                    "SOP_ID", "Keywords", "Tool_Type",
                    "Func_Desc", "Args_Schema", "param_desc",
                ])

        self._tools_df = tools_df
        self._sops_df = sops_df
        self._composite_executor = composite_executor

        # ── atomic_toolbox：从 tools_df 加载（仅 action / gather）──
        self.atomic_toolbox: dict[str, callable] = {}
        for _, row in tools_df.iterrows():
            tool_id = row["Tool_ID"]
            tool_type = row.get("Tool_Type", "action")
            if tool_type != "composite":
                func = self._func_map.get(tool_id)
                if func is not None:
                    self.atomic_toolbox[tool_id] = func

        # ── composite_registry：从 sops_df 加载（所有行均为 composite）──
        self.composite_registry: dict[str, dict] = {}
        for _, row in sops_df.iterrows():
            tool_id = row["SOP_ID"]
            self.composite_registry[tool_id] = {
                "func_desc": row.get("Func_Desc", ""),
                "args_schema": row.get("Args_Schema", "{}"),
                "param_desc": row.get("param_desc", ""),
            }

        # 向后兼容别名（data_nodes/ToolExecutor 等零参构造引用 .toolbox）
        self.toolbox = self.atomic_toolbox

    # ── Composite 识别 ──────────────────────────────────────────

    def is_composite(self, tool_id: str) -> bool:
        """判断 tool_id 是否为 composite（SOP）工具。"""
        return tool_id in self.composite_registry

    def get_composite_ids(self) -> set:
        """返回所有 composite 工具 ID 集合。"""
        return set(self.composite_registry.keys())

    async def dispatch_composite(
        self, tool_id: str, args: dict, **exec_kwargs
    ) -> dict:
        """异步调度 composite 工具，委托给注入的 composite_executor 回调。

        Args:
            tool_id: composite 工具 ID（即 SOP ID）
            args: 工具参数字典
            **exec_kwargs: 透传给 composite_executor 的额外参数
                          （state, resources, app_graph, 等）

        Returns:
            dict: 执行结果（与 execute_sop_flow 返回格式一致）
        """
        if tool_id not in self.composite_registry:
            return {
                "status": "失败",
                "summary": f"未找到 composite 工具: {tool_id}",
                "detail": "",
            }
        if self._composite_executor is None:
            return {
                "status": "失败",
                "summary": "composite_executor 未注入，无法执行 SOP",
                "detail": "",
            }
        return await self._composite_executor(tool_id, args, **exec_kwargs)

    # ── Atomic 调度（同步，供 LangGraph tool_executor_node 使用）──

    def dispatch(self, tool_id: str, args: dict):
        """同步调度 atomic 工具（action / gather）。

        composite 工具请使用 dispatch_composite()。
        """
        if tool_id not in self.atomic_toolbox:
            return {
                "status": "失败",
                "summary": f"未找到工具 ID: {tool_id}",
                "detail": "",
            }
        try:
            resolved_args = {}
            for key, value in args.items():
                if isinstance(value, str) and value.startswith("VAR_"):
                    resolved = resolve_variable(value)
                    if not resolved:
                        return {
                            "status": "失败",
                            "summary": f"变量 {value} 未找到或已过期",
                            "detail": "",
                        }
                    resolved_args[key] = resolved
                else:
                    resolved_args[key] = value

            func = self.atomic_toolbox[tool_id]
            return func(**resolved_args)
        except TypeError as e:
            return {"status": "失败", "summary": f"参数错误: {str(e)}", "detail": ""}
        except Exception as e:
            return {"status": "失败", "summary": f"执行异常: {str(e)}", "detail": ""}

    # ── 参数名获取（atomic 用 inspect，composite 用 args_schema）──

    def get_param_names(self, tool_id: str) -> list[str]:
        """返回工具的参数名列表（按顺序），用于位置参数解析。

        atomic 工具从函数签名提取；composite 工具从 Args_Schema JSON 提取。
        """
        # atomic
        func = self.atomic_toolbox.get(tool_id)
        if func is not None:
            try:
                return list(inspect.signature(func).parameters.keys())
            except (ValueError, TypeError):
                pass

        # composite
        meta = self.composite_registry.get(tool_id)
        if meta is not None:
            try:
                schema = json.loads(meta["args_schema"])
                return list(schema.keys())
            except (json.JSONDecodeError, TypeError):
                pass

        return []
