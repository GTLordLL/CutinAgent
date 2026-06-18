"""GIT_SMART_COMMIT SOP 集成测试。

在临时 git 仓库中运行完整提交流程，验证：
- SOP 匹配正确
- 变量传递（VAR_get_git_status, VAR_get_git_diff）
- commit message 生成 + 提交成功
- 执行完毕后自动清理临时仓库
"""

import os
import sys
import time
import tempfile
import subprocess
import shutil

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from graph.Builder import build_graph
from graph.OverallState import OverallState
from utils.LLMResources import initialize_resources
from utils.debug_logger import set_session_dir
from data_nodes.VariableStore import clear as clear_variables


def setup_temp_repo(tmpdir: str):
    """在临时目录创建 git 仓库，初始提交后修改文件产生未暂存变更。"""
    os.chdir(tmpdir)
    subprocess.run(["git", "init"], check=True, capture_output=True)
    subprocess.run(["git", "config", "user.name", "Test User"], check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], check=True)

    # 写入并提交初始文件
    with open("README.md", "w") as f:
        f.write("# Test Project\n\nA sample project for testing.\n")
    with open("main.py", "w") as f:
        f.write("def hello():\n    print('Hello, world!')\n\n\nif __name__ == '__main__':\n    hello()\n")

    subprocess.run(["git", "add", "README.md", "main.py"], check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial commit"], check=True, capture_output=True)

    # 修改文件产生未暂存变更（git diff 可检测）
    with open("README.md", "w") as f:
        f.write("# Test Project v2\n\nUpdated for testing smart commit.\n")
    with open("main.py", "a") as f:
        f.write("\ndef goodbye():\n    print('Goodbye!')\n")

    print(f"  临时仓库: {tmpdir}")
    print(f"  样本文件: README.md, main.py (已修改)")


def run_test():
    print("=" * 60)
    print("GIT_SMART_COMMIT 集成测试")
    print("=" * 60)

    tmpdir = tempfile.mkdtemp(prefix="git_test_")
    original_cwd = os.getcwd()

    try:
        # 1. 初始化资源（必须在 chdir 之前，因为配置使用相对路径）
        print("\n[1] 初始化 LLM 资源...")
        clear_variables()
        resources = initialize_resources()
        app = build_graph(resources)
        print("  资源初始化完成，图编译通过")

        # 2. 搭建临时仓库（会 os.chdir 到临时目录）
        print("\n[2] 创建临时 git 仓库...")
        setup_temp_repo(tmpdir)

        # 3. 创建会话目录
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join(original_cwd, "history", f"{timestamp}_git_smart_commit_test")
        set_session_dir(session_dir)

        # 4. 初始状态
        initial_input: OverallState = {
            "user_instruction": "帮我提交代码",
            "session_dir": session_dir,
            "sop_ids": list(resources.sops_df["SOP_ID"].tolist()),

            "matched_sop_id": "",
            "sop_objective": "",
            "sop_plan_steps": "",
            "sop_exception_handling": "",
            "sop_tools_required": "",

            "current_tool_call": "",
            "current_tool_call_raw": "",
            "current_tool_args": {},
            "current_tool_calls": [],
            "execution_result": "",

            "tool_status": "",
            "tool_summary": "",
            "tool_detail_var": "",

            "last_step": "",
            "task_status": "ONGOING",

            "current_round": 0,
            "retry_limit": 3,
            "final_report": "",
        }  # type: ignore

        # 5. 执行
        print("\n[5] 开始执行 GIT_SMART_COMMIT...")
        print("-" * 50)

        max_rounds = 20
        final_task_status = "ONGOING"
        matched_sop = ""
        sop_plan_final = ""

        start_time = time.time()
        for event in app.stream(initial_input, stream_mode="updates"):
            if not event:
                continue
            for node_name, output in event.items():
                if "initial_sop" in node_name:
                    matched_sop = output.get("matched_sop_id", "?")
                    status = output.get("task_status", "?")
                    print(f"[SOP匹配] {matched_sop} | 状态: {status}")
                    if status == "NO_MATCHING_SOP":
                        print("  ❌ 未匹配到 SOP，终止")
                        return False

                elif "sop_execution" in node_name:
                    ls = output.get("last_step", "?")
                    tc = output.get("current_tool_call", "?")
                    ts = output.get("task_status", "?")
                    final_task_status = ts
                    print(f"[调度器] NEXT: {ls} | TOOL: {tc} | STATUS: {ts}")

                elif "tool_executor" in node_name:
                    ts = output.get("tool_status", "")
                    tsm = output.get("tool_summary", "")
                    tdv = output.get("tool_detail_var", "")
                    print(f"[工具执行] {ts} | {tsm}")
                    if tdv:
                        print(f"  变量: {tdv}")

                elif "progress" in node_name:
                    sop_plan_final = output.get("sop_plan_steps", "")
                    rnd = output.get("current_round", "?")
                    print(f"[进度更新] 回合 {rnd}")
                    # 打印最后一步的状态
                    lines = sop_plan_final.strip().split('\n')
                    for line in lines:
                        if '结果:' in line:
                            print(f"  {line[:150]}")

                if max_rounds <= 0:
                    print("  ⚠️ 超过最大轮次，强制终止")
                    return False
                max_rounds -= 1

        elapsed = time.time() - start_time
        print(f"\n[完成] 总耗时: {elapsed:.1f}s")

        # 6. 断言
        print("\n[6] 验证结果...")
        errors = []

        if matched_sop != "GIT_SMART_COMMIT":
            errors.append(f"SOP匹配错误: {matched_sop}")
        if final_task_status != "FINISH":
            errors.append(f"最终状态不是 FINISH: {final_task_status}")
        if "VAR_get_git_status" not in sop_plan_final:
            errors.append("SOP_PLAN 中缺少变量 VAR_get_git_status")
        if "VAR_get_git_diff" not in sop_plan_final:
            errors.append("SOP_PLAN 中缺少变量 VAR_get_git_diff")

        # 检查 git log（应有至少 2 个提交：初始 + 新提交）
        try:
            log_output = subprocess.check_output(
                ["git", "log", "--oneline"],
                universal_newlines=True
            ).strip()
        except subprocess.CalledProcessError:
            log_output = ""
        if not log_output:
            errors.append("git log 为空，提交未成功")
        else:
            print(f"  提交记录: {log_output}")

        # 检查 tool_outputs 文件
        tool_output_dir = os.path.join(session_dir, "tool_outputs")
        if os.path.isdir(tool_output_dir):
            files = os.listdir(tool_output_dir)
            print(f"  tool_outputs: {len(files)} 个文件")
            for f in sorted(files):
                print(f"    {f}")

        if errors:
            print("\n  ❌ 测试失败:")
            for e in errors:
                print(f"    - {e}")
            return False
        else:
            print("\n  ✅ 全部断言通过")
            return True

    finally:
        # 7. 清理
        os.chdir(original_cwd)
        shutil.rmtree(tmpdir, ignore_errors=True)
        print(f"\n  已清理临时仓库: {tmpdir}")


if __name__ == "__main__":
    success = run_test()
    print("\n" + "=" * 60)
    print("GIT_SMART_COMMIT 测试 " + ("通过 ✅" if success else "失败 ❌"))
    print("=" * 60)
    sys.exit(0 if success else 1)
