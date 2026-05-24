# QUICK_PORT_CHECK

## Objective
检查指定TCP端口是否在监听，并识别占用该端口的进程。

## Description
简单的端口诊断：确认监听状态并报告绑定的进程。适用于用户询问特定端口号的场景。

## Keywords
NETWORK, ss, netstat, port, listen, tcp

## Tools_Required
check_network_port, generate_summary_report

## Retry_Limit
3

## Plan_Steps
1. 调用 check_network_port(port=用户指定的端口号)，检查该TCP端口是否正在监听以及哪个进程占用了该端口。
2. 调用 generate_summary_report(data=步骤1的端口检查结果)，汇总端口监听状态和占用进程信息生成端口诊断报告。报告需说明端口是否在监听、占用进程名称和PID。如果步骤1返回失败（权限不足或端口号无效），报告需说明失败原因。
3. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，SOP Execution Scheduler 可在 Retry_Limit 内调整参数重试；若问题超出工具能力范围（参考 AVAILABLE_TOOLS 中的 param_desc）或重试耗尽，则继续按后续规则处理。
2. 如果 check_network_port（步骤1）因权限不足（如端口号<1024需root权限）返回失败，标记为 ERROR 并终止，告知用户使用 sudo 重试。
3. 如果 check_network_port（步骤1）因端口号无效返回失败，标记为 ERROR 并终止，告知用户检查端口号是否合法（1-65535）。
4. 如果 generate_summary_report（步骤2）失败，直接输出步骤1的原始端口检查数据作为替代结果。
5. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
