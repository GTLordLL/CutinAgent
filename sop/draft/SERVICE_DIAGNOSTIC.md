# SERVICE_DIAGNOSTIC

## Objective
诊断 systemd 服务故障，检查服务状态、端口监听和最近的错误日志。

## Description
针对任何异常或故障的服务，调查其运行状态、网络绑定和日志内容，确定根本原因。适用于用户报告服务宕机、失败或异常行为的场景。

## Keywords
SERVICE, systemctl, journalctl, port, log, grep, diagnose, failure, docker, nginx, apache, mysql

## Tools_Required
get_service_status, check_network_port, grep_log_content, generate_summary_report

## Retry_Limit
3

## Plan_Steps
1. 调用 get_service_status(service_name=用户指定的服务名称)，获取该服务的运行状态（active/inactive/failed）和最近的错误日志行。
2. 如果步骤1的服务状态为 failed 且错误日志中包含 critical 或 fatal 关键词，就 INTERRUPT，等待用户确认是否继续后续诊断步骤。
3. 如果步骤1的服务状态数据显示该服务需要监听网络端口（如 nginx 对应80和443、mysql 对应3306），就调用 check_network_port(port=服务对应的端口号)，验证端口是否正在监听。如果该服务不涉及网络端口，就跳过本步骤。
4. 基于步骤1的错误日志中提取的关键词列表，同时为其中每一个关键词调用 grep_log_content(path=/var/log/{service_name}/, keyword=该关键词, lines=50)，检索更详细的故障上下文。如果错误日志中无关键词，就跳过本步骤。
5. 调用 generate_summary_report(data=前面所有步骤采集的诊断数据)，汇总所有诊断信息生成服务诊断报告，一切正常也需要报告。
6. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，SOP Execution Scheduler 可在 Retry_Limit 内调整参数重试；若问题超出工具能力范围（参考 AVAILABLE_TOOLS 中的 param_desc）或重试耗尽，则继续按后续规则处理。
2. 如果 get_service_status（步骤1）失败，标记为 ERROR 并终止，告知用户检查服务名称是否正确以及当前用户是否有 systemctl 权限。
3. 如果 check_network_port（步骤3）失败，标记为 ERROR 并终止，告知用户端口检查失败。
4. 如果 grep_log_content（步骤4）返回的结果不符合预期，按规则1重试；若全部关键词均重试耗尽，标记为 ERROR 并终止。
5. 如果 generate_summary_report（步骤5）失败，输出前面所有步骤已采集的原始数据作为替代报告。
6. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止，输出已采集的部分诊断数据并建议人工介入。
