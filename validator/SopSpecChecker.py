"""SOP Plan_Steps 严格 DSL 格式校验器。

在 SOP 加载时调用，确保 Plan_Steps 符合代码可解析的格式规范。
校验失败直接拒绝加载，避免运行时解析出错。
"""

import re
from dataclasses import dataclass, field
from parsers.sop_plan import StepType, _classify_step, _extract_tool_ids


@dataclass
class SopSpecError:
    line_number: int
    step_number: int
    message: str
    severity: str = "ERROR"


def _check_interrupt_in_text(text: str, step_type: StepType) -> bool:
    """检查 INTERRUPT/ERROR 是否出现在不允许的位置。
    允许：终止步骤本身、条件分支内（如果...就 INTERRUPT）。
    禁止：顺序/并行/迭代步骤的正文中。
    """
    if step_type in (StepType.INTERRUPT, StepType.ERROR, StepType.FINISH):
        return True

    # 提取不含条件子句的文本部分
    no_conds = re.sub(r'如果[^。]*就[^。]*。', '', text)
    no_conds = re.sub(r'如果[^。]*就[^。]*$', '', no_conds)

    # 如果原文本有 INTERRUPT 但都在条件子句里 → 允许
    interrupt_outside = 'INTERRUPT' in no_conds
    error_outside = 'ERROR' in no_conds and step_type != StepType.ERROR

    return not (interrupt_outside or error_outside)


# ── main checker ─────────────────────────────────────────

def check_sop_plan_steps(
    plan_steps_text: str,
    valid_tool_ids: set[str],
) -> list[SopSpecError]:
    """校验 Plan_Steps 是否符合严格 DSL 格式。
    Returns: 错误列表。空列表 = 合法。
    """
    errors: list[SopSpecError] = []
    lines = plan_steps_text.strip().split('\n')

    parsed: list[tuple[int, str, StepType]] = []  # (num, raw_text, type)
    step_numbers: set[int] = set()
    max_step = 0

    # ── Pass 1: parse each line ──
    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue

        ln = idx + 1  # 1-indexed for error reporting
        m = re.match(r'^(\d+)\.\s+(.*)', line)
        if not m:
            errors.append(SopSpecError(
                ln, 0,
                f"行不以 'N. ' 开头，内容: '{line[:60]}'"
            ))
            continue

        num = int(m.group(1))
        text = m.group(2).strip()
        step_type = _classify_step(text)

        # 序号不能重复
        if num in step_numbers:
            errors.append(SopSpecError(
                ln, num,
                f"步骤序号 {num} 重复出现"
            ))
        step_numbers.add(num)
        max_step = max(max_step, num)

        # 未知类型
        if step_type == StepType.UNKNOWN:
            errors.append(SopSpecError(
                ln, num,
                f"无法识别步骤类型，内容: '{text[:80]}'。"
                f"必须包含 '调用'/'如果...就'/'同时调用'/'FINISH' 之一"
            ))

        # INTERRUPT/ERROR 不在允许位置
        if not _check_interrupt_in_text(text, step_type):
            errors.append(SopSpecError(
                ln, num,
                f"INTERRUPT/ERROR 在不允许的位置出现。"
                f"仅允许作为终止步骤或条件分支内的 INTERRUPT"
            ))

        # 提取并校验工具 ID
        tool_ids = _extract_tool_ids(text)
        for tid in tool_ids:
            if tid not in valid_tool_ids:
                errors.append(SopSpecError(
                    ln, num,
                    f"工具 ID '{tid}' 不在 tools.csv 中"
                ))

        # 顺序步骤必须至少引用一个工具
        if step_type == StepType.SEQUENTIAL and not tool_ids:
            errors.append(SopSpecError(
                ln, num,
                f"顺序步骤必须包含 '调用 tool_id(...)' 格式的工具调用"
            ))

        # 并行步骤最多 3 个工具
        if step_type == StepType.PARALLEL and len(tool_ids) > 3:
            errors.append(SopSpecError(
                ln, num,
                f"并行步骤最多同时调用 3 个工具，当前 {len(tool_ids)} 个"
            ))

        # 条件步骤必须有 "如果...就" 模式
        if step_type == StepType.CONDITIONAL:
            if not re.search(r'如果.+就', text):
                errors.append(SopSpecError(
                    ln, num,
                    f"条件步骤缺少 '如果...就...' 句式"
                ))

        parsed.append((num, text, step_type))

    # ── Pass 2: global checks ──

    if not parsed:
        errors.append(SopSpecError(0, 0, "Plan_Steps 为空"))
        return errors

    # 序号连续性 (1..max_step 无跳空)
    expected = set(range(1, max_step + 1))
    missing = expected - step_numbers
    if missing:
        errors.append(SopSpecError(
            0, 0,
            f"步骤序号不连续，缺少: {sorted(missing)}"
        ))

    # 最后一步必须是 FINISH
    last_num, last_text, last_type = parsed[-1]
    if last_type != StepType.FINISH:
        errors.append(SopSpecError(
            0, last_num,
            f"最后一步必须是 FINISH，当前为 {last_type.value.upper()}。"
            f"每个 SOP 必须以 FINISH 显式声明终止"
        ))

    # 至少有一个 FINISH
    finish_count = sum(1 for _, _, t in parsed if t == StepType.FINISH)
    if finish_count == 0:
        errors.append(SopSpecError(0, 0, "Plan_Steps 缺少 FINISH 终止标记"))
    # 允许多个 FINISH：条件分支中可提前 FINISH，只要最后一步是 FINISH 即可

    return errors


def check_retry_limit(retry_limit_text: str) -> list[SopSpecError]:
    """校验 Retry_Limit 字段是否为合法正整数。
    Returns: 错误列表。空列表 = 合法。
    """
    errors: list[SopSpecError] = []
    text = retry_limit_text.strip()
    if not text:
        errors.append(SopSpecError(
            0, 0,
            "Retry_Limit 字段为空或缺失，必须设置为正整数（如 3）"
        ))
        return errors
    if not text.isdigit():
        errors.append(SopSpecError(
            0, 0,
            f"Retry_Limit 必须为正整数，当前值: '{text}'"
        ))
        return errors
    val = int(text)
    if val < 1:
        errors.append(SopSpecError(
            0, 0,
            f"Retry_Limit 必须 >= 1，当前值: {val}"
        ))
    return errors
