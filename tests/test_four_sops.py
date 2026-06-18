"""批量测试操作类 Git SOP：GIT_SMART_COMMIT, GIT_BRANCH_CLEANUP。

在 tests/demo_environments/ 预搭建的 tmp 仓库中运行完整 SOP 流程。
每个 SOP 先加载 markdown 填充 state，再执行图，最后 TaskCompactor。
"""

import os
import sys
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from graph.Builder import build_graph
from utils.LLMResources import initialize_resources
from utils.sop_loader import load_sop_markdown
from utils.debug_logger import set_session_dir
from data_nodes.VariableStore import clear as clear_variables
from repl.execution.sop_runner import _iterate_graph_stream
from repl.execution.llm_runner import run_llm_node_sync
from llm_nodes.TaskCompactorNode import task_compactor_node
from repl.state.state_manager import reset_sop_state

# 颜色
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_RED = "\033[31m"
C_YELLOW = "\033[33m"
C_CYAN = "\033[36m"
C_RESET = "\033[0m"

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TMP_DIR = os.path.join(PROJECT_ROOT, "tmp")

DEMOS = {
    "GIT_SMART_COMMIT": {
        "dir": os.path.join(TMP_DIR, "demo_smart_commit"),
        "instruction": "帮我提交当前的变更",
    },
    "GIT_BRANCH_CLEANUP": {
        "dir": os.path.join(TMP_DIR, "demo_branch_cleanup"),
        "instruction": "帮我清理过期的已合并分支",
    },
}


def run_sop_test(sop_id: str, resources, app_graph, original_cwd: str) -> dict:
    """执行单个 SOP 测试。

    1. 加载 SOP markdown → 填充 state
    2. 运行 SOP 执行图
    3. 运行 TaskCompactor
    4. 断言验证
    """
    demo_dir = DEMOS[sop_id]["dir"]
    instruction = DEMOS[sop_id]["instruction"]

    result = {
        "sop": sop_id,
        "passed": False,
        "final_task_status": "",
        "total_rounds": 0,
        "elapsed": 0,
        "errors": [],
        "sop_plan_final": "",
        "tool_outputs": [],
    }

    try:
        os.chdir(demo_dir)

        # 清变量 + 创建会话目录
        clear_variables()
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        session_dir = os.path.join(original_cwd, "history", f"{timestamp}_{sop_id.lower()}_test")
        os.makedirs(session_dir, exist_ok=True)
        set_session_dir(session_dir)

        # ── 1. 加载 SOP markdown ──
        valid_tool_ids = set(resources.tools_df["Tool_ID"].tolist())
        try:
            sop_md = load_sop_markdown(sop_id, resources.sop_dir, valid_tool_ids)
        except ValueError as e:
            result["errors"].append(f"SOP 加载失败: {e}")
            return result

        # ── 2. 构建初始 state ──
        state = {}
        state["user_instruction"] = instruction
        state["session_dir"] = session_dir
        state["sop_ids"] = list(resources.sops_df["SOP_ID"].tolist())

        state["matched_sop_id"] = sop_id
        state["sop_objective"] = sop_md.get("objective", "")
        state["sop_plan_steps"] = sop_md.get("plan_steps", "")
        state["sop_tools_required"] = sop_md.get("tools_required", "")
        state["sop_exception_handling"] = sop_md.get("exception_handling", "")
        state["retry_limit"] = (
            int(sop_md.get("retry_limit", "3").strip())
            if sop_md.get("retry_limit", "3").strip().isdigit()
            else 3
        )

        state["current_tool_call"] = ""
        state["current_tool_call_raw"] = ""
        state["current_tool_args"] = {}
        state["current_tool_calls"] = []
        state["execution_result"] = ""
        state["tool_status"] = ""
        state["tool_summary"] = ""
        state["tool_detail_var"] = ""
        state["last_step"] = ""
        state["task_status"] = "ONGOING"
        state["current_round"] = 0
        state["final_report"] = ""

        print(f"  SOP 加载: {sop_id} | 工具: {state['sop_tools_required']}")

        # ── 3. 运行 SOP 执行图 ──
        start_time = time.time()
        state, node_timings, final_task_status, total_rounds, node_outputs = (
            _iterate_graph_stream(app_graph, state, node_callback=None)
        )
        sop_elapsed = time.time() - start_time

        # 收集工具输出
        for no in node_outputs:
            if no["node_name"] == "tool_executor":
                result["tool_outputs"].append({
                    "status": no["output"].get("tool_status", ""),
                    "summary": no["output"].get("tool_summary", ""),
                })

        # ── 4. TaskCompactor ──
        try:
            compactor_fn = task_compactor_node(resources, headless=True)
            compactor_result, _ = run_llm_node_sync("TaskCompactor", compactor_fn, state)
            state.update(compactor_result)
        except Exception as e:
            print(f"  {C_YELLOW}TaskCompactor 失败（非致命）: {e}{C_RESET}")

        total_elapsed = time.time() - start_time
        result["elapsed"] = total_elapsed
        result["final_task_status"] = final_task_status
        result["total_rounds"] = total_rounds
        result["sop_plan_final"] = state.get("sop_plan_steps", "")

        # ── 5. 断言 ──
        if final_task_status != "FINISH":
            result["errors"].append(f"最终状态不是 FINISH: {final_task_status}")

        # 检查 SOP_PLAN 中有无步骤被标记结果
        plan = result["sop_plan_final"]
        if "结果:" not in plan and "中断已完成" not in plan:
            result["errors"].append("SOP_PLAN 中无任何步骤被标记完成")

        # 检查是否产生了工具输出
        if not result["tool_outputs"]:
            result["errors"].append("无任何工具执行记录")

        if not result["errors"]:
            result["passed"] = True

        return result

    except Exception as e:
        import traceback
        result["errors"].append(f"执行崩溃: {e}\n{traceback.format_exc()}")
        return result

    finally:
        os.chdir(original_cwd)


def main():
    print("=" * 60)
    print("  批量测试操作类 Git SOP")
    print("=" * 60)

    original_cwd = os.getcwd()

    # 0. 初始化资源（全局一次）
    print(f"\n{C_BOLD}[0] 初始化 LLM 资源...{C_RESET}")
    try:
        clear_variables()
        resources = initialize_resources()
        app_graph = build_graph(resources, headless=True)
        print("  资源初始化完成，图编译通过")
    except Exception as e:
        print(f"  {C_RED}资源初始化失败: {e}{C_RESET}")
        return 1

    # 1. 重建所有演示环境
    print(f"\n{C_BOLD}[1] 重建演示环境...{C_RESET}")
    from tests.demo_environments.demo_smart_commit import setup_demo_smart_commit
    from tests.demo_environments.demo_branch_cleanup import setup_demo_branch_cleanup

    setup_demo_smart_commit(os.path.join(TMP_DIR, "demo_smart_commit"))
    setup_demo_branch_cleanup(os.path.join(TMP_DIR, "demo_branch_cleanup"))

    # 2. 依次测试
    results = {}
    for sop_id in DEMOS:
        print(f"\n{C_BOLD}{'─'*60}{C_RESET}")
        print(f"{C_BOLD}[测试] {sop_id}{C_RESET}")
        print(f"  指令: {DEMOS[sop_id]['instruction']}")
        print(f"{C_BOLD}{'─'*60}{C_RESET}")

        result = run_sop_test(sop_id, resources, app_graph, original_cwd)
        results[sop_id] = result

        # 打印结果
        if result["passed"]:
            print(f"\n  {C_GREEN}✅ {sop_id} 通过{C_RESET} "
                  f"(耗时: {result['elapsed']:.1f}s, 轮次: {result['total_rounds']})")
        else:
            print(f"\n  {C_RED}❌ {sop_id} 失败{C_RESET} "
                  f"(耗时: {result['elapsed']:.1f}s, 状态: {result['final_task_status']})")
            for e in result["errors"]:
                print(f"    - {e}")

        # 打印工具执行摘要
        if result["tool_outputs"]:
            print(f"\n  {C_YELLOW}工具执行记录:{C_RESET}")
            for i, to in enumerate(result["tool_outputs"]):
                print(f"    [{to['status']}] {to['summary'][:120]}")

        # 打印最终 SOP_PLAN
        plan = result.get("sop_plan_final", "")
        if plan:
            lines = plan.strip().split('\n')
            print(f"\n  {C_YELLOW}最终 SOP_PLAN:{C_RESET}")
            for line in lines:
                print(f"    {line[:160]}")

    # 3. 汇总
    print(f"\n{C_BOLD}{'='*60}{C_RESET}")
    print(f"{C_BOLD}  测试汇总{C_RESET}")
    print(f"{C_BOLD}{'='*60}{C_RESET}")

    total = len(results)
    passed = sum(1 for r in results.values() if r["passed"])
    failed = total - passed

    for sop_id, r in results.items():
        status = f"{C_GREEN}PASS{C_RESET}" if r["passed"] else f"{C_RED}FAIL{C_RESET}"
        print(f"  [{status}] {sop_id}  ({r['elapsed']:.1f}s, {r['total_rounds']}r, "
              f"→{r['final_task_status']})")
        if r["errors"]:
            for e in r["errors"]:
                print(f"         {C_RED}{e}{C_RESET}")

    print(f"\n  {passed}/{total} 通过", end="")
    if failed > 0:
        print(f", {C_RED}{failed} 失败{C_RESET}")
    else:
        print(f" {C_GREEN}✅{C_RESET}")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
