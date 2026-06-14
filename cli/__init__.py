"""CutinAgent Headless CLI 包。

提供 cutin run 命令的入口和 Headless 执行编排。

注意：为避免导入 ollama 等重型依赖，各模块按需导入。
"""

# 轻量模块（无 LLM 依赖）直接导出
from cli.output_formatter import HeadlessRunResult, format_plain, format_json


def get_parser():
    """懒加载 cli.parser（避免 ollama 初始化）。"""
    from cli.parser import build_parser
    return build_parser()


def get_runner():
    """懒加载 cli.headless_runner（避免 ollama 初始化）。"""
    from cli.headless_runner import run_headless
    return run_headless


__all__ = ["HeadlessRunResult", "format_plain", "format_json", "get_parser", "get_runner"]
