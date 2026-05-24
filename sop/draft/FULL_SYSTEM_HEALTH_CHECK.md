# FULL_SYSTEM_HEALTH_CHECK

## Objective
执行全面的系统健康检查，覆盖CPU、内存、负载、磁盘、进程和时间同步，生成最终汇总报告。

## Description
通过采集各子系统指标并综合分析，诊断系统整体健康状态。适用于用户要求检查系统状态、性能概览或全面诊断的场景。

## Keywords
SYSTEM_STATUS, health, scan, cpu, memory, load, disk, process, time, full-check, comprehensive, status, all

## Tools_Required
get_system_health, list_top_processes, check_system_sync, generate_summary_report

## Retry_Limit
3

## Plan_Steps
1. 同时调用 get_system_health(target='all') 和 check_system_sync()，并行采集系统资源指标（CPU、内存、负载、磁盘）和时钟同步状态。
2. 如果步骤1的系统资源数据中CPU使用率超过80%或内存使用率超过90%，就调用 list_top_processes(sort_by='cpu', limit=10)，识别当前资源占用最高的进程列表。如果所有指标正常，就跳过本步骤。
3. 调用 generate_summary_report(data=前面所有步骤采集的系统指标数据)，汇总所有采集数据生成系统健康检查报告。报告需标注各资源使用率、异常进程、时间同步状态。
4. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，SOP Execution Scheduler 可在 Retry_Limit 内调整参数重试；若问题超出工具能力范围（参考 AVAILABLE_TOOLS 中的 param_desc）或重试耗尽，则继续按后续规则处理。
2. 如果 get_system_health 或 check_system_sync（步骤1）失败，标记为 ERROR 并终止，告知用户检查系统权限。
3. 如果 list_top_processes（步骤2）失败，标记为 ERROR 并终止，告知用户进程列表采集失败。
4. 如果 generate_summary_report（步骤3）失败，输出步骤1和步骤2已采集的原始数据作为替代报告，标记为 ERROR。
5. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止，输出已采集的部分数据并建议人工介入。
