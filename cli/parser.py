"""Headless CLI 参数解析（argparse）。"""

import argparse


def build_parser() -> argparse.ArgumentParser:
    """构建 cutin run 子命令的 argparse 解析器。"""
    parser = argparse.ArgumentParser(
        prog="cutin run",
        description="CutinAgent Headless 模式 —— 直接执行 SOP 并输出结果。",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  cutin run --sop GIT_SMART_COMMIT "提交当前变更"
  cutin run --sop GIT_DAILY_SUMMARY --output json "汇总今日提交"
  cutin run --output json "帮我看看Git状态"
  cutin run --stream "分析一下代码变更"
        """,
    )

    parser.add_argument(
        "instruction",
        type=str,
        help="用户指令（自然语言描述想做什么）",
    )

    parser.add_argument(
        "--sop",
        type=str,
        default=None,
        metavar="SOP_ID",
        help="跳过 UserCoordinator，直接执行此 SOP（如 GIT_SMART_COMMIT）",
    )

    parser.add_argument(
        "--auto-confirm",
        action="store_true",
        default=False,
        help="跳过所有确认步骤（指定 --sop 时已隐式生效）",
    )

    parser.add_argument(
        "--output",
        type=str,
        choices=["plain", "json", "json-full"],
        default="json",
        help="输出格式 (默认: json 最小化；json-full 完整调试；plain 人类可读)",
    )

    stream_group = parser.add_mutually_exclusive_group()
    stream_group.add_argument(
        "--stream",
        action="store_true",
        dest="stream",
        default=False,
        help="实时流式输出 LLM token 到 stdout",
    )
    stream_group.add_argument(
        "--no-stream",
        action="store_false",
        dest="stream",
        help="静默执行，仅输出最终结果 (默认)",
    )

    parser.add_argument(
        "--timeout",
        type=int,
        default=300,
        metavar="SECONDS",
        help="最大执行时间，秒 (默认: 300)",
    )

    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        default=False,
        help="详细调试输出",
    )

    return parser
