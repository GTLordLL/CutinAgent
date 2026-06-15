"""演示 4：GIT_REPO_HEALTH — 仓库健康检查。

场景：模拟长期维护后略显凌乱的仓库，适合全面体检。
- 5 个本地分支：2 个过期已合并 + 1 个活跃未合并 + 1 个可能废弃
- 混乱工作区：1 已暂存 + 1 已修改 + 3 未跟踪
- 近 7 天 4 条直接提交 + 2 条 merge commit
"""

import os
import shutil

from tests.demo_utils import (
    C_CYAN, C_GREEN, C_RESET,
    date_days_ago, git_add_commit, git_init, run, write_file,
)


def setup_demo_repo_health(repo_dir):
    """搭建演示4仓库：模拟长期维护后略显凌乱的仓库，适合全面体检。"""
    print(f"  {C_CYAN}[演示4] 搭建 GIT_REPO_HEALTH 演示环境 ...{C_RESET}")

    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)

    git_init(repo_dir)
    run(["git", "branch", "-M", "main"], cwd=repo_dir)

    # -- 初始提交 (main) --
    write_file(repo_dir, "README.md", "# DataPipeline\n\n数据处理流水线项目。\n")
    write_file(repo_dir, "src/__init__.py", "")
    write_file(repo_dir, "src/pipeline.py", '''\
"""数据处理流水线核心模块。"""
from typing import Iterator


class Pipeline:
    def __init__(self, name: str = "default"):
        self.name = name
        self.stages: list = []

    def add_stage(self, stage):
        self.stages.append(stage)
        return self

    def run(self, data: Iterator) -> Iterator:
        result = data
        for stage in self.stages:
            result = stage(result)
        return result
''')
    write_file(repo_dir, "src/transformers.py", '''\
"""数据变换器集合。"""
from typing import Iterator


def filter_none(data: Iterator) -> Iterator:
    return (item for item in data if item is not None)


def normalize(data: Iterator) -> Iterator:
    for item in data:
        if isinstance(item, str):
            yield item.strip().lower()
        else:
            yield item
''')
    write_file(repo_dir, "requirements.txt", "pyyaml==6.0.1\n")
    git_add_commit(repo_dir, "feat(pipeline): 初始化数据处理流水线框架",
                   date_str=date_days_ago(7))

    # -- 最近 7 天的提交 --
    write_file(repo_dir, "src/validators.py", '''\
"""数据校验模块。"""
from typing import Optional


def validate_schema(data: dict, required_fields: list[str]) -> Optional[str]:
    for field in required_fields:
        if field not in data:
            return f"缺少必需字段: {field}"
    return None


def validate_types(data: dict, field_types: dict[str, type]) -> list[str]:
    errors = []
    for field, expected_type in field_types.items():
        if field in data and not isinstance(data[field], expected_type):
            errors.append(f"字段 {field} 类型错误: 期望 {expected_type.__name__}")
    return errors
''')
    git_add_commit(repo_dir, "feat(validators): 添加 schema 和类型校验",
                   date_str=date_days_ago(5))

    write_file(repo_dir, "src/pipeline.py", '''\
"""数据处理流水线核心模块（含执行日志）。"""
import logging
from typing import Iterator, Optional

logger = logging.getLogger(__name__)


class PipelineError(Exception):
    """流水线执行错误。"""
    def __init__(self, stage_name: str, original_error: Exception):
        self.stage_name = stage_name
        self.original_error = original_error
        super().__init__(f"阶段 '{stage_name}' 执行失败: {original_error}")


class Pipeline:
    def __init__(self, name: str = "default"):
        self.name = name
        self.stages: list = []
        self.error_policy: str = "raise"  # raise / skip / warn

    def add_stage(self, stage, name: Optional[str] = None):
        stage_name = name or getattr(stage, "__name__", "unknown")
        self.stages.append((stage_name, stage))
        return self

    def run(self, data: Iterator) -> Iterator:
        logger.info(f"流水线 '{self.name}' 开始执行，共 {len(self.stages)} 个阶段")
        result = data
        for stage_name, stage_fn in self.stages:
            try:
                logger.debug(f"执行阶段: {stage_name}")
                result = stage_fn(result)
            except Exception as e:
                logger.error(f"阶段 '{stage_name}' 失败: {e}")
                if self.error_policy == "raise":
                    raise PipelineError(stage_name, e)
                elif self.error_policy == "skip":
                    continue
                # warn: 继续但记录
        logger.info(f"流水线 '{self.name}' 执行完毕")
        return result
''')
    git_add_commit(repo_dir, "fix(pipeline): 添加阶段级错误处理和三种容错策略",
                   date_str=date_days_ago(3))

    write_file(repo_dir, "README.md", '''\
# DataPipeline — 数据处理流水线

可组合的数据处理流水线框架，支持 Schema 校验和错误恢复。

## 快速开始

```python
from src.pipeline import Pipeline
from src.transformers import filter_none, normalize

pipeline = Pipeline("cleanup")
pipeline.add_stage(filter_none).add_stage(normalize)
result = list(pipeline.run(iter([None, " Hello ", "", "WORLD"])))
# => ['hello', 'world']
```

## 模块

- `src/pipeline.py` — 流水线引擎（含容错策略）
- `src/transformers.py` — 内置变换器
- `src/validators.py` — Schema 与类型校验
''')
    git_add_commit(repo_dir, "docs(readme): 补充快速开始示例和模块说明",
                   date_str=date_days_ago(1))

    # -- 过期已合并分支：feature-parquet (merged, 30 days ago) --
    # 使用 --no-ff 避免 fast-forward 导致提交日期乱序
    run(["git", "checkout", "-b", "feature-parquet"], cwd=repo_dir)
    write_file(repo_dir, "src/parquet_reader.py", '''\
"""Parquet 文件读取器。"""
import pyarrow.parquet as pq


def read_parquet(path: str) -> list[dict]:
    table = pq.read_table(path)
    return table.to_pydict()
''')
    git_add_commit(repo_dir, "feat(parquet): 实现 Parquet 文件读取支持",
                   date_str=date_days_ago(30))
    run(["git", "checkout", "main"], cwd=repo_dir)
    run(["git", "merge", "--no-ff", "feature-parquet", "-m",
         "merge: 合并 feature-parquet — Parquet 文件读取支持"], cwd=repo_dir)

    # -- 过期已合并分支：bugfix-encoding (merged, 50 days ago) --
    run(["git", "checkout", "-b", "bugfix-encoding"], cwd=repo_dir)
    write_file(repo_dir, "src/transformers.py", '''\
"""数据变换器集合。"""
from typing import Iterator


def filter_none(data: Iterator) -> Iterator:
    return (item for item in data if item is not None)


def normalize(data: Iterator) -> Iterator:
    for item in data:
        if isinstance(item, str):
            yield item.strip().lower()
        else:
            yield item


def fix_encoding(data: Iterator) -> Iterator:
    """修复常见编码问题。"""
    for item in data:
        if isinstance(item, str):
            try:
                item = item.encode("latin-1").decode("utf-8")
            except (UnicodeDecodeError, UnicodeEncodeError):
                pass
        yield item
''')
    git_add_commit(repo_dir, "fix(encoding): 修复文本管道中的 Latin-1/UTF-8 编码错乱",
                   date_str=date_days_ago(50))
    run(["git", "checkout", "main"], cwd=repo_dir)
    run(["git", "merge", "--no-ff", "bugfix-encoding", "-m",
         "merge: 合并 bugfix-encoding — 编码修复"], cwd=repo_dir)

    # -- 活跃未合并分支：feature-metrics (unmerged, 3 days ago) — 应保留 --
    run(["git", "checkout", "-b", "feature-metrics"], cwd=repo_dir)
    write_file(repo_dir, "src/metrics.py", '''\
"""流水线执行指标收集（WIP）。"""
import time


class MetricsCollector:
    def __init__(self):
        self.stage_timings: dict[str, float] = {}
        self.total_items = 0
        self.error_count = 0

    def record(self, stage: str, duration: float):
        self.stage_timings[stage] = duration

    def summary(self) -> dict:
        return {
            "total_items": self.total_items,
            "error_count": self.error_count,
            "stage_timings": self.stage_timings,
        }
''')
    git_add_commit(repo_dir, "feat(metrics): 实现流水线指标收集器（WIP）",
                   date_str=date_days_ago(3))

    # -- 废弃未合并分支：experiment-grpc (unmerged, 60 days ago) — 可能废弃 --
    run(["git", "checkout", "main"], cwd=repo_dir)
    run(["git", "checkout", "-b", "experiment-grpc"], cwd=repo_dir)
    write_file(repo_dir, "src/grpc_server.py", '''\
"""gRPC 服务端实验代码（未完成）。"""
# TODO: 使用 grpcio 替代当前 HTTP 传输层
# 实验中断 — 不确定 gRPC 是否适合小数据量场景
import grpc
''')
    git_add_commit(repo_dir, "experiment(grpc): gRPC 传输层原型探索（未完成）",
                   date_str=date_days_ago(60))

    # -- 回到 main，制造工作区混乱 --
    run(["git", "checkout", "main"], cwd=repo_dir)

    # 未暂存修改：README.md
    write_file(repo_dir, "README.md", '''\
# DataPipeline — 数据处理流水线

可组合的数据处理流水线框架，支持 Schema 校验、错误恢复和执行指标收集。

## 快速开始

```python
from src.pipeline import Pipeline
from src.transformers import filter_none, normalize, fix_encoding

pipeline = Pipeline("cleanup")
pipeline.add_stage(filter_none).add_stage(normalize).add_stage(fix_encoding)
result = list(pipeline.run(iter([None, " Hello ", "", "WORLD"])))
# => ['hello', 'world']
```

## 模块

- `src/pipeline.py` — 流水线引擎（含三种容错策略）
- `src/transformers.py` — 内置变换器（含编码修复）
- `src/validators.py` — Schema 与类型校验
- `src/metrics.py` — 执行指标收集器

## 配置

支持 YAML 配置文件，通过环境变量 `PIPELINE_CONFIG` 指定路径。
''')

    # 新增未跟踪文件（模拟 build 产物和 IDE 临时文件）
    write_file(repo_dir, "dist/pipeline.tar.gz", "\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03\x00\x00\x00\x00\x00\x00\x00\x00")
    write_file(repo_dir, ".vscode/settings.json", '{\n  "python.linting.enabled": true,\n  "editor.tabSize": 4\n}\n')
    write_file(repo_dir, "debug.log", "2024-06-01 10:00:00 DEBUG Starting pipeline...\n2024-06-01 10:00:01 ERROR Failed to connect to DB\n" * 20)

    # 已暂存变更：src/config.py（模拟暂存但未提交）
    write_file(repo_dir, "src/config.py", '''\
"""全局配置管理（基于 YAML）。"""
import os
import yaml

_config: dict = {}


def load_config(path: str = None):
    global _config
    if path is None:
        path = os.getenv("PIPELINE_CONFIG", "config/default.yaml")
    with open(path, "r") as f:
        _config = yaml.safe_load(f)


def get(key: str, default=None):
    return _config.get(key, default)
''')
    run(["git", "add", "src/config.py"], cwd=repo_dir)

    print(f"         {C_GREEN}仓库就绪{C_RESET}: 5 个本地分支 + 混乱工作区")
    print(f"           main (HEAD)            — 当前分支")
    print(f"           feature-parquet        — 已合并，30天前 → 应清理")
    print(f"           bugfix-encoding        — 已合并，50天前 → 应清理")
    print(f"           feature-metrics        — 未合并，3天前  → 保留（活跃开发中）")
    print(f"           experiment-grpc        — 未合并，60天前 → 可能废弃")
    print(f"           工作区: 1 已暂存 (src/config.py) + 1 已修改 (README.md) + 3 未跟踪 (dist/, .vscode/, debug.log)")
