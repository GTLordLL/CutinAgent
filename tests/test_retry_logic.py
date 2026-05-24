"""测试 ProgressUpdater 重试逻辑。

覆盖场景：
  1. 失败 → 重试成功（retry 计数递增）
  2. 成功 → LLM 决定重新执行（触发重试计数）
  3. 达到重试上限（显示上限标记）
  4. 已跳过步骤被重新执行（清理跳过标记）
"""

import sys
sys.path.insert(0, '/data/gtlord/Desktop/cutin_agent')

from data_nodes.ProgressUpdater import (
    progress_updater_node,
    _parse_steps,
    _reconstruct_plan,
    _already_has_result,
    _extract_retry_count,
    _is_step_marked,
)


def make_state(sop_plan_steps, last_step, tool_call_raw,
               status, conclusion, summary="", detail_var="",
               retry_limit=3, current_round=0):
    return {
        "sop_plan_steps": sop_plan_steps,
        "last_step": last_step,
        "current_tool_call_raw": tool_call_raw,
        "tool_status": status,
        "tool_conclusion": conclusion,
        "tool_summary": summary,
        "tool_detail_var": detail_var,
        "retry_limit": retry_limit,
        "current_round": current_round,
    }


def test_failure_then_retry_success():
    """场景1：步骤失败 → 无重试标记(首次) → LLM重试 → 重试 1/3"""
    plan = (
        "1. 调用 check_network_port(port=22)\n"
        "2. FINISH。"
    )
    # 第1次执行：失败（首次执行，无 结果: 标记，走 _update_sequential）
    state = make_state(plan, "1. 调用 check_network_port(port=22)",
                       "check_network_port(port=22)",
                       "失败", "连接被拒绝")
    result = progress_updater_node(state)
    plan1 = result["sop_plan_steps"]
    print(f"  第1次(失败): {plan1}")
    assert "结果: 失败 | 连接被拒绝" in plan1
    assert "重试" not in plan1, "首次执行不应有重试计数"

    # 第2次执行：LLM 决定重试（已有 结果:，走 _update_with_retry）
    state2 = make_state(plan1, "1. 调用 check_network_port(port=22)",
                        "check_network_port(port=22)",
                        "失败", "权限不足")
    result2 = progress_updater_node(state2)
    plan2 = result2["sop_plan_steps"]
    print(f"  第2次(重试): {plan2}")
    assert "重试 1/3" in plan2, f"应有 重试 1/3: {plan2}"
    assert "权限不足" in plan2
    assert "连接被拒绝" not in plan2, "旧结果应被剥离"

    # 第3次执行：LLM 再次重试（改参数后成功）
    state3 = make_state(plan2, "1. 调用 check_network_port(port=22)",
                        "check_network_port(port=22)",
                        "成功", "端口22处于监听状态",
                        "端口22 LISTEN", "VAR_get_git_status")
    result3 = progress_updater_node(state3)
    plan3 = result3["sop_plan_steps"]
    print(f"  第3次(成功): {plan3}")
    assert "重试 2/3" in plan3, f"应有 重试 2/3: {plan3}"
    assert "成功 | 端口22处于监听状态" in plan3
    assert "[变量: VAR_get_git_status]" in plan3
    assert plan3.count("结果:") == 1, f"不应有双 结果:: {plan3}"

    print("  ✅ 场景1 通过\n")


def test_success_then_retry():
    """场景2：步骤成功后 LLM 决定重新执行 → 触发重试计数"""
    plan = (
        "1. 调用 locate_large_files(path=/var/log, limit=5)\n"
        "2. FINISH。"
    )
    # 首次执行：成功
    state = make_state(plan, "1. 调用 locate_large_files(path=/var/log, limit=5)",
                       "locate_large_files(path=/var/log, limit=5)",
                       "成功", "找到3个大文件",
                       "syslog(1.2G), kern.log(800M), auth.log(500M)",
                       "VAR_locate_large_files")
    result = progress_updater_node(state)
    plan1 = result["sop_plan_steps"]
    print(f"  首次(成功): {plan1}")
    assert "结果: 成功" in plan1
    assert "找到3个大文件" in plan1
    assert "[变量: VAR_locate_large_files]" in plan1
    assert "重试" not in plan1, "首次成功不应有重试标记"

    # LLM 决定重新执行（换个参数重试）
    state2 = make_state(plan1, "1. 调用 locate_large_files(path=/var/log, limit=5)",
                        "locate_large_files(path=/var/log, limit=5)",
                        "成功", "找到5个大文件",
                        "syslog(1.2G), kern.log(800M), auth.log(500M), dpkg.log(300M), syslog.1(200M)",
                        "VAR_locate_large_files_2")
    result2 = progress_updater_node(state2)
    plan2 = result2["sop_plan_steps"]
    print(f"  重试(成功): {plan2}")
    assert "重试 1/3" in plan2, f"重试应有计数: {plan2}"
    assert plan2.count("结果:") == 1, f"不应有双 结果:: {plan2}"
    assert "找到3个大文件" not in plan2, f"旧结果应被剥离: {plan2}"
    assert "找到5个大文件" in plan2, f"新结果应出现: {plan2}"

    print("  ✅ 场景2 通过\n")


def test_retry_limit_exceeded():
    """场景3：重试次数达到上限 → 显示已达到重试上限"""
    plan = (
        "1. 调用 check_system_sync()\n"
        "2. FINISH。"
    )
    # 第1次：失败（首次执行，无重试标记）
    state = make_state(plan, "1. 调用 check_system_sync()",
                       "check_system_sync()",
                       "失败", "无法获取系统同步状态",
                       retry_limit=1)
    result = progress_updater_node(state)
    plan1 = result["sop_plan_steps"]
    print(f"  第1次(首次失败,limit=1): {plan1}")
    assert "重试" not in plan1, "首次执行不应有重试计数"

    # 第2次：LLM 重试 → 重试 1/1（达到上限）
    state2 = make_state(plan1, "1. 调用 check_system_sync()",
                        "check_system_sync()",
                        "失败", "权限不足，无法获取系统同步状态",
                        retry_limit=1)
    result2 = progress_updater_node(state2)
    plan2 = result2["sop_plan_steps"]
    print(f"  第2次(重试,达上限): {plan2}")
    assert "重试 1/1" in plan2, f"应有 重试 1/1: {plan2}"

    # 第3次：继续重试（已超上限）
    state3 = make_state(plan2, "1. 调用 check_system_sync()",
                        "check_system_sync()",
                        "失败", "仍旧无法获取系统同步状态",
                        retry_limit=1)
    result3 = progress_updater_node(state3)
    plan3 = result3["sop_plan_steps"]
    print(f"  第3次(超限): {plan3}")
    assert "已达到重试上限（1次）" in plan3, f"应有上限标记: {plan3}"
    assert plan3.count("结果:") == 1, f"不应有双 结果:: {plan3}"

    print("  ✅ 场景3 通过\n")


def test_skipped_step_reexecuted():
    """场景4：已跳过步骤被 LLM 决定重新执行 → 清理跳过标记"""
    plan = (
        "1. 如果端口80有监听，就调用 check_network_port(port=80)。"
        "如果端口8080有监听，就调用 check_network_port(port=8080)。\n"
        "2. 调用 get_service_status(service='nginx')\n"
        "3. FINISH。"
    )
    # 模拟步骤1已执行（条件命中），步骤2已标记跳过
    plan_with_skip = (
        "1. 因为端口80有监听，所以调用 check_network_port(port=80) "
        "结果: 成功 | 端口80处于监听状态 | 端口80 LISTEN [变量: VAR_check_network_port]。\n"
        "2. 调用 get_service_status(service='nginx') 已跳过（条件不满足）。\n"
        "3. FINISH。"
    )

    # LLM 决定重新执行步骤2（原来被跳过的）
    state = make_state(plan_with_skip, "2. 调用 get_service_status(service='nginx')",
                       "get_service_status(service='nginx')",
                       "成功", "nginx 服务正在运行，PID 1234",
                       "Active: active (running)", "VAR_get_service_status")
    result = progress_updater_node(state)
    plan_out = result["sop_plan_steps"]
    print(f"  重新执行已跳过步骤: {plan_out}")
    assert "已跳过" not in plan_out, f"跳过标记应被清理: {plan_out}"
    assert "结果: 成功 | nginx 服务正在运行" in plan_out
    assert "[变量: VAR_get_service_status]" in plan_out
    # 第2行的步骤不应有双 结果:
    line2 = plan_out.split('\n')[1]
    assert line2.count("结果:") == 1, f"步骤2不应有双 结果:: {line2}"

    print("  ✅ 场景4 通过\n")


def test_no_double_result_mark():
    """场景5：任何情况下都不应出现双 结果: 标记"""
    plan = (
        "1. 调用 locate_large_files(path=/tmp, limit=10)\n"
        "2. FINISH。"
    )
    # 连续执行3次（模拟LLM反复重试且每次都成功）
    state = make_state(plan, "1. 调用 locate_large_files(path=/tmp, limit=10)",
                       "locate_large_files(path=/tmp, limit=10)",
                       "成功", "找到0个大文件",
                       "(empty)", "VAR_locate_large_files")
    result = progress_updater_node(state)
    plan_cur = result["sop_plan_steps"]
    assert plan_cur.count("结果:") == 1

    for i in range(2):
        state_r = make_state(plan_cur, "1. 调用 locate_large_files(path=/tmp, limit=10)",
                             "locate_large_files(path=/tmp, limit=10)",
                             "成功", "找到0个大文件",
                             "(empty)", "VAR_locate_large_files_2")
        result = progress_updater_node(state_r)
        plan_cur = result["sop_plan_steps"]
        assert plan_cur.count("结果:") == 1, f"第{i+2}次执行出现双结果: {plan_cur}"

    print(f"  最终: {plan_cur}")
    print("  ✅ 场景5 通过\n")


if __name__ == '__main__':
    print("=" * 60)
    print("ProgressUpdater 重试逻辑测试")
    print("=" * 60 + "\n")

    test_failure_then_retry_success()
    test_success_then_retry()
    test_retry_limit_exceeded()
    test_skipped_step_reexecuted()
    test_no_double_result_mark()

    print("=" * 60)
    print("全部测试通过 ✅")
    print("=" * 60)
