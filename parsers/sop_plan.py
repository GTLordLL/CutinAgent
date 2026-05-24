import re
from enum import Enum


class StepType(Enum):
    FINISH = "finish"
    INTERRUPT = "interrupt"
    ERROR = "error"
    PARALLEL = "parallel"
    CONDITIONAL = "conditional"
    SEQUENTIAL = "sequential"
    UNKNOWN = "unknown"


def _extract_tool_ids(text: str) -> list[str]:
    """从文本中提取所有 tool_id(...) 中的 tool_id。"""
    return re.findall(r'(\w+)\(', text)


def _classify_step(text: str) -> StepType:
    """根据文本内容分类步骤类型。按优先级从高到低匹配。"""
    t = text.strip()

    # 1) 终止标记
    if re.match(r'^FINISH[。.]?$', t):
        return StepType.FINISH
    if re.match(r'^INTERRUPT', t):
        return StepType.INTERRUPT
    if re.match(r'^ERROR[。.]?$', t):
        return StepType.ERROR

    # 2) 并行（静态并行 + 动态集合并行）
    if ('同时调用' in t or ('基于' in t and '同时为其中每一个' in t)) and '调用' in t:
        return StepType.PARALLEL

    # 3) 条件选择
    if '如果' in t and '就' in t:
        return StepType.CONDITIONAL

    # 4) 顺序执行
    if '调用' in t:
        return StepType.SEQUENTIAL

    return StepType.UNKNOWN


# ── plan text parsing ────────────────────────────────────

def _parse_steps(plan_text: str) -> list[dict]:
    """将 SOP_PLAN 文本解析为步骤块列表。
    Returns: [{number, header, sub_lines, original_header}, ...]
    """
    steps = []
    current = None
    for line in plan_text.split('\n'):
        m = re.match(r'^(\d+)\.\s+(.*)', line)
        if m:
            if current is not None:
                steps.append(current)
            current = {
                'number': int(m.group(1)),
                'header': m.group(2).strip(),
                'sub_lines': [],
                '_leading': line[:m.start()],
            }
        elif current is not None and line.strip():
            current['sub_lines'].append(line)
    if current is not None:
        steps.append(current)
    return steps


def _reconstruct_plan(steps: list[dict]) -> str:
    """将步骤块列表重建为 SOP_PLAN 文本字符串。"""
    lines = []
    for s in steps:
        lines.append(f"{s['number']}. {s['header']}")
        for sub in s['sub_lines']:
            lines.append(sub)
    return '\n'.join(lines)
