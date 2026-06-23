"""Headless 模式主编排器。

将 CLI args 转化为完整的 SOP 执行流程，输出结构化结果。
"""

import sys
import time
import signal

from utils.LLMResources import initialize_resources
from utils.sop_loader import load_sop_markdown
from graph.Builder import build_graph
from llm_nodes.UserCoordinatorNode import user_coordinator_node
from llm_nodes.SopSummarizerNode import sop_summarizer_node
from repl.state.state_manager import create_initial_state
from repl.state.session_manager import generate_session_id, create_session_dir, write_run_summary
from repl.execution.llm_runner import run_llm_node_sync
from repl.execution.execution_controller import execute_sop_flow_headless
from tools.ToolDispatcher import ToolDispatcher
from cli.output_formatter import HeadlessRunResult, format_plain, format_json, format_json_full


class TimeoutError(Exception):
    """SOP 执行超时。"""
    pass


def _timeout_handler(signum, frame):
    raise TimeoutError("执行超时")


def _make_headless_composite_executor():
    """工厂函数：返回 headless 版 composite 工具执行回调。

    与 main.py 的 _make_composite_executor 对应，但委派给 execute_sop_flow_headless。
    """
    async def _exec(sop_id, args, **exec_kwargs):
        state = exec_kwargs.pop("state", {})
        state["matched_sop_id"] = sop_id
        if args:
            args_str = ", ".join(
                f"{k}={repr(v)}" for k, v in args.items()
            )
            state["tool_call"] = f"{sop_id}({args_str})"
        else:
            state["tool_call"] = f"{sop_id}()"
        return execute_sop_flow_headless(state=state, **exec_kwargs)
    return _exec


def run_headless(args) -> int:
    """Headless 模式主入口。

    Args:
        args: argparse.Namespace（由 cli.parser 解析）

    Returns:
        int: exit code（0 成功，1 失败）
    """
    t_total_start = time.time()

    # ── 1. 初始化资源 ──
    try:
        resources = initialize_resources()
    except Exception as e:
        result = HeadlessRunResult(
            status="error",
            error=f"资源初始化失败: {e}",
        )
        _output(result, args)
        return 1

    # ── 2. 编译 SOP 执行图（headless 模式，无终端输出）──
    app_graph = build_graph(resources, headless=True)

    # ── 2b. 创建 ToolDispatcher（headless composite_executor 闭包）──
    tool_dispatcher = ToolDispatcher(
        tools_df=resources.tools_df,
        composite_executor=_make_headless_composite_executor(),
    )

    # ── 3. 会话目录 ──
    session_dir = args.session_dir if hasattr(args, 'session_dir') and args.session_dir else create_session_dir()
    session_id = generate_session_id()
    all_sop_ids = list(resources.sops_df["SOP_ID"].tolist())

    # ── 4. 校验 SOP_ID（如果指定）──
    if args.sop:
        if args.sop not in all_sop_ids:
            result = HeadlessRunResult(
                status="error",
                sop_id=args.sop,
                error=f"无效的 SOP_ID: {args.sop}。可用: {', '.join(all_sop_ids)}",
            )
            _output(result, args)
            return 1

    # ── 5. 设置超时 ──
    timeout = getattr(args, 'timeout', 300)
    if timeout > 0:
        signal.signal(signal.SIGALRM, _timeout_handler)
        signal.alarm(timeout)

    try:
        # ── 6. 创建初始 State ──
        state = create_initial_state(args.instruction, session_dir, all_sop_ids)
        state["session_id"] = session_id

        if args.sop:
            # ── Path A: 直接执行指定 SOP ──
            result = _execute_direct_sop(state, resources, app_graph, args, session_dir)
        else:
            # ── Path B: 先跑 UserCoordinator 匹配 SOP ──
            result = _execute_with_coordinator(state, resources, app_graph, args, session_dir)

    except TimeoutError:
        result = HeadlessRunResult(
            status="error",
            sop_id=getattr(args, 'sop', ''),
            error=f"执行超时（{timeout}s）",
            total_duration_s=time.time() - t_total_start,
        )
    except Exception as e:
        import traceback
        result = HeadlessRunResult(
            status="error",
            sop_id=getattr(args, 'sop', ''),
            error=f"未预期的错误: {e}\n{traceback.format_exc()}",
            total_duration_s=time.time() - t_total_start,
        )
    finally:
        signal.alarm(0)  # 取消超时

    # ── 7. 输出结果 ──
    _output(result, args)
    return 0 if result.status == "success" else 1


def _execute_direct_sop(state, resources, app_graph, args, session_dir) -> HeadlessRunResult:
    """Path A: 跳过 UserCoordinator，直接执行指定 SOP。

    加载 SOP markdown，填充 state 的 SOP 字段，设置 IS_EXECUTE=true，
    然后进入 execute_sop_flow_headless。
    """
    valid_tool_ids = set(resources.tools_df["Tool_ID"].tolist())

    # 加载 SOP
    try:
        sop_md = load_sop_markdown(args.sop, resources.sop_dir, valid_tool_ids)
    except ValueError as e:
        return HeadlessRunResult(
            status="error",
            sop_id=args.sop,
            error=f"SOP 加载失败: {e}",
        )

    # 填充 state
    state["matched_sop_id"] = args.sop
    state["sop_objective"] = sop_md.get("objective", "")
    state["sop_plan_steps"] = sop_md.get("plan_steps", "")
    state["sop_tools_required"] = sop_md.get("tools_required", "")
    state["sop_exception_handling"] = sop_md.get("exception_handling", "")
    state["retry_limit"] = (
        int(sop_md.get("retry_limit", "3").strip())
        if sop_md.get("retry_limit", "3").strip().isdigit()
        else 3
    )
    state["tool_call"] = f"{args.sop}()"

    # 构建 TaskCompactor（headless 模式：不输出到终端）
    sop_summarizer_fn = sop_summarizer_node(resources, headless=True)

    return execute_sop_flow_headless(
        state=state,
        resources=resources,
        app_graph=app_graph,
        valid_tool_ids=valid_tool_ids,
        sop_summarizer_fn=sop_summarizer_fn,
        session_dir=session_dir,
    )


def _execute_with_coordinator(state, resources, app_graph, args, session_dir) -> HeadlessRunResult:
    """Path B: 通过 UserCoordinator 匹配 SOP 后再执行。

    UserCoordinator 的三阶段确认在单次调用中完成——
    如果 IS_EXECUTE=true，立即执行；否则返回 CHAT_MESSAGE。
    """
    coordinator_fn = user_coordinator_node(resources, headless=True)
    sop_summarizer_fn = sop_summarizer_node(resources, headless=True)
    valid_tool_ids = set(resources.tools_df["Tool_ID"].tolist())

    # 运行 UserCoordinator
    coord_result, coord_elapsed = run_llm_node_sync(
        "UserCoordinator", coordinator_fn, state
    )
    state.update(coord_result)

    chat_message = state.get("chat_message", "")
    tool_call = state.get("tool_call", "")
    matched_sop = state.get("matched_sop_id", "")

    if not tool_call or tool_call == "NONE":
        # 规划阶段：agent 还在收集信息或确认意图
        return HeadlessRunResult(
            status="success",
            sop_id=matched_sop,
            chat_message=chat_message,
            user_message=chat_message,
            task_status="PLANNING",
            total_duration_s=coord_elapsed,
        )

    # TOOL_CALL 非 NONE → 执行 SOP
    if not matched_sop or matched_sop not in set(resources.sops_df["SOP_ID"].tolist()):
        return HeadlessRunResult(
            status="error",
            sop_id=matched_sop,
            error=f"UserCoordinator 返回了无效的 SOP_ID: {matched_sop}",
            chat_message=chat_message,
        )

    return execute_sop_flow_headless(
        state=state,
        resources=resources,
        app_graph=app_graph,
        valid_tool_ids=valid_tool_ids,
        sop_summarizer_fn=sop_summarizer_fn,
        session_dir=session_dir,
    )


def _output(result, args):
    """根据 --output 参数输出格式化结果。

    规则：
    - --output plain  → 人类可读全文（保持原样）
    - --output json   → 最小化 JSON（-v 时升级为完整输出）
    - --output json-full → 完整 JSON（含 node_outputs / compactor / variables）
    - 错误时：最小化 JSON 也会自动附带 debug 信息
    """
    if isinstance(result, HeadlessRunResult):
        pass
    elif isinstance(result, dict):
        # 兼容 execute_sop_flow_headless 返回 dict 的情况
        r = HeadlessRunResult()
        r.status = result.get("status", "success")
        r.sop_id = result.get("sop_id", "")
        r.task_status = result.get("task_status", "")
        r.chat_message = result.get("chat_message", "")
        r.total_rounds = result.get("total_rounds", 0)
        r.total_duration_s = result.get("total_duration_s", 0)
        r.node_outputs = result.get("node_outputs", [])
        r.sop_summary = result.get("sop_summary", "")
        r.variables = result.get("variables", {})
        r.final_report = result.get("final_report", "")
        r.session_dir = result.get("session_dir", "")
        r.error = result.get("error")
        result = r

    output_fmt = getattr(args, 'output', 'json')
    verbose = getattr(args, 'verbose', False)

    if output_fmt == 'plain':
        print(format_plain(result))
    elif output_fmt == 'json-full' or verbose:
        # 显式完整输出 / -v 强制调试
        print(format_json_full(result))
    else:
        # 默认 json：最小化（错误自动展开）
        print(format_json(result))
