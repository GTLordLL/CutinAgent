import readline
import time
from datetime import datetime
from graph.Builder import build_graph
from utils.LLMResources import initialize_resources
from utils.sop_loader import load_sop_markdown
from utils.debug_logger import set_session_dir
from llm_nodes.UserCoordinatorNode import user_coordinator_node
from llm_nodes.CompactorNode import compactor_node
from repl import (
    create_initial_state,
    create_session_dir,
    dispatch_repl_command,
    reset_sop_state,
    run_sop_graph,
    write_run_summary,
)


_REPL_COMMANDS = ["/help", "/sops", "/history", "/clear", "/exit", "/quit"]


def _repl_completer(text: str, state: int) -> str | None:
    """readline tab 补全函数：匹配 / 前缀命令。"""
    matches = [c for c in _REPL_COMMANDS if c.startswith(text)]
    return matches[state] if state < len(matches) else None


def run_repl():
    """REPL 主循环：资源初始化 → 交互循环
       (UserCoordinator → 确认 → SOP 执行 → Compactor)。
    """
    # 1. 初始化资源
    print("正在初始化 LLM 资源与知识库...")
    resources = initialize_resources()

    # 2. 编译 SOP 执行图（3 节点内循环）
    app = build_graph(resources)

    # 3. 创建 UserCoordinator 和 Compactor 可调用对象
    user_coordinator_fn = user_coordinator_node(resources)
    compactor_fn = compactor_node(resources)

    # 4. 创建会话目录
    session_dir = create_session_dir()
    set_session_dir(session_dir)
    print(f"会话目录: {session_dir}")

    # 5. 初始化 state
    state = create_initial_state("", session_dir, resources.sop_library_text)
    valid_tool_ids = set(resources.tools_df["Tool_ID"].tolist())

    print("\n" + "=" * 60)
    print("  CutinAgent REPL — 人机协作模式")
    print("  /help 查看命令  /exit 退出")
    print("=" * 60)

    # 注册 tab 补全
    readline.set_completer_delims(" \t\n")
    readline.set_completer(_repl_completer)
    readline.parse_and_bind("tab: complete")

    # 6. REPL 循环
    while True:
        user_msg = input("\n> ").strip()
        if not user_msg:
            continue

        # / 命令分发（在 UserCoordinator 之前拦截，不消耗 LLM）
        handled, msg, should_exit = dispatch_repl_command(user_msg, state, resources)
        if should_exit:
            print(msg)
            break
        if handled:
            print(f"\n{msg}")
            continue

        # 追加到当前对话
        state["current_dialogue"] += f"User: {user_msg}\n"
        state["user_instruction"] = user_msg

        # ---- Step 1: UserCoordinator ----
        print("\n[UserCoordinator] 分析中...")
        coord_result = user_coordinator_fn(state)
        state.update(coord_result)

        # 始终显示聊天消息
        print(f"\n[Cutin Agent] {state['chat_message']}")

        # 始终追加 Agent 消息到对话历史（渐进式确认需要追踪每一轮）
        state["current_dialogue"] += f"Agent: {state['chat_message']}\n"

        # ---- Step 2: 判断模式 ----
        if state.get("is_execute") == "true":
            # 最终确认模式：所有细节已确认，展示摘要，等待用户最终许可
            print(f"\n{'='*50}")
            print(f"[确认执行] {state['matched_sop_id']}")
            print(f"[行动] {state['current_action']}")
            print(f"[长期计划] {state['long_term_intent']}")
            print(f"{'='*50}")

            confirm = input("\n确认执行? (y=执行 / n=重新规划 / 或输入补充信息): ").strip()

            if confirm.lower() != 'y':
                # 用户拒绝或提供补充信息 → 作为新一轮输入
                if confirm.lower() != 'n':
                    user_msg = confirm
                else:
                    user_msg = input("请重新描述您的需求: ").strip()
                    if not user_msg:
                        continue
                state["current_dialogue"] += f"User (feedback): {user_msg}\n"
                state["user_instruction"] = user_msg
                continue

            # ---- Step 3: 加载 SOP → 执行 SOP 图 ----
            try:
                sop_md = load_sop_markdown(state["matched_sop_id"], resources.sop_dir, valid_tool_ids)
            except ValueError as e:
                print(f"\n[错误] SOP 加载失败: {e}")
                state["current_dialogue"] += f"Agent (error): SOP load failed: {e}\n"
                continue

            # 保存 REPL 字段，重置 SOP 状态
            saved_sop_id = state["matched_sop_id"]
            saved_action = state["current_action"]
            saved_long_term = state["long_term_intent"]
            state = reset_sop_state(state)
            state.update({
                "matched_sop_id": saved_sop_id,
                "sop_objective": sop_md.get("objective", ""),
                "sop_plan_steps": sop_md.get("plan_steps", ""),
                "sop_tools_required": sop_md.get("tools_required", ""),
                "sop_exception_handling": sop_md.get("exception_handling", ""),
                "retry_limit": int(sop_md.get("retry_limit", "3").strip()) if sop_md.get("retry_limit", "3").strip().isdigit() else 3,
                "user_instruction": saved_action,
                "current_action": saved_action,
                "long_term_intent": saved_long_term,
                "task_status": "ONGOING",
                "current_round": 0,
            })

            print(f"\n[执行] 开始执行 SOP: {state['matched_sop_id']}")
            print(f"[行动] {state['user_instruction']}")
            print("-" * 50)

            sop_start = time.time()
            try:
                state, node_timings, final_task_status, total_rounds = run_sop_graph(app, state)
            except Exception as e:
                print(f"\n[错误] SOP 执行崩溃: {e}")
                import traceback
                traceback.print_exc()
                state["current_dialogue"] += f"Agent (error): SOP execution failed: {e}\n"
                continue

            sop_elapsed = time.time() - sop_start
            print(f"\n[SOP 执行完毕] 状态: {final_task_status} | 耗时: {sop_elapsed:.2f}s | 轮次: {total_rounds}")

            # ---- Step 4: Compactor ----
            print("\n[Compactor] 评价与总结中...")
            compactor_result = compactor_fn(state)
            state.update(compactor_result)

            print(f"\n[执行评价] {state['compactor_evaluation']}")

            satisfied = input("\n对执行结果满意吗? (y/n): ").strip()

            if satisfied.lower() == 'y':
                if state["compactor_conversation_summary"]:
                    state["conversation_history"] += "\n" + state["compactor_conversation_summary"]
                if state["compactor_execution_summary"]:
                    state["execution_history"] += "\n" + state["compactor_execution_summary"]
                state["current_dialogue"] = ""  # 满意后才清除对话
                print("[Agent] 总结已记录。请继续下一个任务。")
            else:
                print("[Agent] 总结未记录。请告诉我如何调整？")

            # 写运行摘要
            write_run_summary(
                session_dir=session_dir,
                user_query=state.get("current_action", ""),
                start_dt=datetime.fromtimestamp(sop_start),
                end_dt=datetime.fromtimestamp(sop_start + sop_elapsed),
                elapsed=sop_elapsed,
                node_timings=node_timings,
                final_task_status=final_task_status,
                total_rounds=total_rounds,
            )
        else:
            # 渐进式确认模式（IS_EXECUTE=false）：继续循环，等待用户下一轮输入
            pass


if __name__ == "__main__":
    run_repl()
