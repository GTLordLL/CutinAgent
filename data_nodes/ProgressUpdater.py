"""进度更新器 —— 纯 Python 代码替代 ProgressSummarizerV2。

接收 ToolExecutor 的执行结果（四字段），以机械方式更新 SOP_PLAN 中的进度标记。
不调用 LLM，不总结执行结果。
"""

import re
import os
import time
from datetime import datetime
from parsers.sop_plan import _classify_step, StepType, _parse_steps, _reconstruct_plan


# ── skip gap detection ───────────────────────────────────

def _is_step_marked(step: dict) -> bool:
    """检查步骤是否已有任何状态标记（含 header 和 sub_lines）。"""
    markers = ("结果:", "已跳过", "重试 ", "已达到重试上限", "中断已完成")
    text = step['header']
    for sub in step['sub_lines']:
        text += ' ' + sub.strip()
    return any(m in text for m in markers)


def _find_previous_marked_step(steps: list[dict], before_num: int) -> int | None:
    """找到 before_num 之前最近一个已有标记的步骤号，没有则返回 None。"""
    best = None
    for s in steps:
        if s['number'] < before_num and _is_step_marked(s):
            if best is None or s['number'] > best:
                best = s['number']
    return best


def _fill_skipped_gaps(steps: list[dict], from_num: int, to_num: int):
    """将 from_num+1 到 to_num-1 之间未标记的步骤标记为已跳过。"""
    for s in steps:
        if from_num < s['number'] < to_num and not _is_step_marked(s):
            s['header'] = f"{s['header']} 已跳过（条件不满足）。"
            s['sub_lines'] = []


# ── result formatting ────────────────────────────────────

def _format_result(status: str, conclusion: str, summary: str,
                   detail_var: str) -> str:
    """根据四字段拼接执行结果字符串。"""
    if status == "失败":
        return f"{status} | {conclusion}"
    parts = [status, conclusion]
    if summary:
        parts.append(summary)
    result = " | ".join(parts)
    if detail_var:
        result += f" [变量: {detail_var}]"
    return result


# ── helpers ──────────────────────────────────────────────

def _extract_retry_count(step: dict) -> int:
    """从步骤 header 中提取当前重试次数。未找到返回 0。"""
    m = re.search(r'重试\s+(\d+)/\d+', step['header'])
    if m:
        return int(m.group(1))
    return 0


def _already_has_result(step: dict) -> bool:
    """检测步骤是否已有结果标记（非首次执行）。"""
    return '结果:' in step['header']


# ── update handlers ──────────────────────────────────────

def _update_sequential(step: dict, tool_call_raw: str,
                       status: str, conclusion: str,
                       summary: str, detail_var: str):
    """顺序/并行步骤：拼接四字段到步骤标题。"""
    formatted = _format_result(status, conclusion, summary, detail_var)
    base = re.sub(r'\s*已跳过.*$', '', step['header'])
    step['header'] = f"{base} 结果: {formatted}。"
    step['sub_lines'] = []


def _update_conditional(step: dict, tool_call_raw: str,
                        status: str, conclusion: str,
                        summary: str, detail_var: str):
    """条件步骤：匹配分支，输出 '因为...所以...' """
    formatted = _format_result(status, conclusion, summary, detail_var)
    base = re.sub(r'\s*已跳过.*$', '', step['header'])
    branches = re.findall(r'如果(.+?)，就\s*调用\s*(\w+)\(', base)

    taken_condition = None
    for cond, tool_id in branches:
        if tool_id in tool_call_raw:
            taken_condition = cond.strip()
            break

    if taken_condition:
        step['header'] = (
            f"因为{taken_condition}，所以调用 {tool_call_raw} 结果: {formatted}。"
        )
    else:
        step['header'] = f"{base} 结果: {formatted}。"
    step['sub_lines'] = []


def _update_interrupt(step: dict):
    """INTERRUPT 步骤：写入中断已完成标记。"""
    base = re.sub(r'\s*已跳过.*$', '', step['header'])
    step['header'] = f"{base} 中断已完成，请继续执行。"
    step['sub_lines'] = []


def _update_with_retry(step: dict, tool_call_raw: str,
                       status: str, conclusion: str,
                       summary: str, detail_var: str,
                       retry_limit: int):
    """重新执行时的重试标记：追加重试计数或上限标记。"""
    formatted = _format_result(status, conclusion, summary, detail_var)
    current_retry = _extract_retry_count(step)
    next_retry = current_retry + 1

    base = step['header']
    base = re.sub(r'\s*结果:\s*.*$', '', base)
    base = re.sub(r'\s*重试\s+\d+/\d+.*$', '', base)
    base = re.sub(r'\s*已达到重试上限.*$', '', base)
    base = re.sub(r'\s*已跳过.*$', '', base)

    if next_retry <= retry_limit:
        step['header'] = (
            f"{base} 结果: {formatted}。重试 {next_retry}/{retry_limit}"
        )
    else:
        step['header'] = (
            f"{base} 结果: {formatted}。"
            f"已达到重试上限（{retry_limit}次），当前步骤不允许再次重试。"
        )
    step['sub_lines'] = []


# ── main node ────────────────────────────────────────────

def _log_progress_update(session_dir: str, round_num: int, target_num: int,
                          plan_before: str, plan_after: str,
                          gaps_filled: bool, step_type, is_retry: bool,
                          elapsed_seconds: float):
    """将 ProgressUpdater 本次更新写入日志文件。"""
    if not session_dir:
        return
    target_dir = os.path.join(session_dir, f"round_{round_num}")
    os.makedirs(target_dir, exist_ok=True)
    filename = f"{target_dir}/ProgressUpdater.txt"
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(filename, "w", encoding="utf-8") as f:
        f.write(f"{'='*60}\n")
        f.write(f"Node: ProgressUpdater | Round: {round_num} | Time: {ts}\n")
        f.write(f"{'='*60}\n\n")
        f.write(f"target_step: {target_num}\n")
        f.write(f"step_type: {step_type.name if step_type else 'UNKNOWN'}\n")
        f.write(f"is_retry: {is_retry}\n")
        f.write(f"gaps_filled: {gaps_filled}\n")
        f.write(f"elapsed: {elapsed_seconds:.4f}s\n\n")
        f.write("--- SOP_PLAN (before) ---\n")
        f.write(plan_before + "\n\n")
        f.write("--- SOP_PLAN (after) ---\n")
        f.write(plan_after + "\n")


def progress_updater_node(state: dict) -> dict:
    """纯 Python 进度更新节点。不调用 LLM。

    Input (from state):
        sop_plan_steps: 当前 Plan_Steps 文本
        last_step: SOP Execution Scheduler 输出的 NEXT_STEP
        current_tool_call_raw: 刚被 ToolExecutor 执行过的工具调用字符串
        tool_status: "成功" / "失败"
        tool_conclusion: 结论/原因
        tool_summary: 精简数据
        tool_detail_var: 变量名 VAR_xxx（可为空）
        retry_limit: SOP 全局重试上限
        current_round: 当前回合数

    Output:
        sop_plan_steps: 更新后的 Plan_Steps
        current_round: 递增 1
    """
    t_start = time.time()
    sop_plan = state.get("sop_plan_steps", "")
    last_step = state.get("last_step", "")
    tool_call_raw = state.get("current_tool_call_raw", "")
    status = state.get("tool_status", "")
    conclusion = state.get("tool_conclusion", "")
    summary = state.get("tool_summary", "")
    detail_var = state.get("tool_detail_var", "")
    retry_limit = state.get("retry_limit", 3)
    current_round = state.get("current_round", 0)
    session_dir = state.get("session_dir", "")

    # 提取目标步骤编号
    step_match = re.match(r'^(\d+)', last_step.strip())
    if not step_match:
        return {"sop_plan_steps": sop_plan, "current_round": current_round + 1}

    target_num = int(step_match.group(1))

    # 解析现有 Plan
    steps = _parse_steps(sop_plan)
    if not steps:
        return {"sop_plan_steps": sop_plan, "current_round": current_round + 1}

    # 定位目标步骤
    target = None
    for s in steps:
        if s['number'] == target_num:
            target = s
            break

    if target is None:
        return {"sop_plan_steps": sop_plan, "current_round": current_round + 1}

    # 填补跳过步骤间隙
    gaps_filled = False
    prev_marked = _find_previous_marked_step(steps, target_num)
    if prev_marked is not None and prev_marked < target_num - 1:
        _fill_skipped_gaps(steps, prev_marked, target_num)
        gaps_filled = True

    # 分类并更新
    step_type = _classify_step(target['header'])
    is_retry = _already_has_result(target)

    if is_retry:
        _update_with_retry(target, tool_call_raw,
                           status, conclusion, summary, detail_var,
                           retry_limit)
    elif step_type in (StepType.SEQUENTIAL, StepType.PARALLEL):
        _update_sequential(target, tool_call_raw,
                           status, conclusion, summary, detail_var)
    elif step_type == StepType.CONDITIONAL:
        _update_conditional(target, tool_call_raw,
                            status, conclusion, summary, detail_var)
    elif step_type == StepType.INTERRUPT:
        _update_interrupt(target)
    # FINISH / ERROR: 不处理

    updated_plan = _reconstruct_plan(steps)
    elapsed = time.time() - t_start

    _log_progress_update(session_dir, current_round, target_num,
                          sop_plan, updated_plan,
                          gaps_filled, step_type, is_retry, elapsed)

    return {
        "sop_plan_steps": updated_plan,
        "current_round": current_round + 1,
    }
