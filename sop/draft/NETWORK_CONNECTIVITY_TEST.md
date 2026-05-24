# NETWORK_CONNECTIVITY_TEST

## Objective
测试与远程主机的网络连通性并诊断路径问题。

## Description
验证远程主机或IP是否可达，测量延迟，检查是否存在丢包或DNS解析问题。

## Keywords
NETWORK, ping, curl, connectivity, latency, host, ip, reachable

## Tools_Required
test_connection, generate_summary_report

## Retry_Limit
3

## Plan_Steps
1. 调用 test_connection(target=用户指定的目标主机名或IP地址)，测试网络连通性，获取延迟时间、丢包率和连接状态结论。
2. 调用 generate_summary_report(data=步骤1的连通性测试结果)，汇总连通性测试结果生成网络诊断报告。报告需说明目标是否可达、平均延迟和丢包率。如果连接失败，报告需分析可能原因（DNS解析失败、防火墙阻断、目标不可达）并给出排查建议。
3. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，SOP Execution Scheduler 可在 Retry_Limit 内调整参数重试；若问题超出工具能力范围（参考 AVAILABLE_TOOLS 中的 param_desc）或重试耗尽，则继续按后续规则处理。
2. 如果 test_connection（步骤1）因DNS解析失败返回错误，建议用户检查目标主机名拼写或尝试使用IP地址，标记为 ERROR 并终止。
3. 如果 test_connection（步骤1）因超时返回错误，标记为 ERROR 并终止，告知用户目标不可达。
4. 如果 generate_summary_report（步骤2）失败，直接输出步骤1的原始连通性测试数据作为替代结果。
5. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
