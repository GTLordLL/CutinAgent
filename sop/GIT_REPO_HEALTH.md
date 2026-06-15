# GIT_REPO_HEALTH

## Objective
对当前 Git 仓库进行全面健康检查，生成包含工作区状态、分支健康度、提交活跃度和改进建议的综合报告。

## Description
组合 get_git_status、get_git_branches、get_git_log 三个只读工具，获取仓库全景数据后通过 LLM 生成结构化健康报告。适用于用户要求"检查仓库健康"、"仓库体检"或"看看仓库有什么问题"的场景。纯只读，零风险。

## Keywords
GIT, health, check, report, status, branch, log, audit

## Tools_Required
get_git_status, get_git_branches, get_git_log, generate_repo_health

## Retry_Limit
3

## Plan_Steps
1. 同时调用 get_git_status()、get_git_branches() 和 get_git_log(since="7days", limit=100)，并行采集工作区状态、分支列表和近7天提交记录。
2. 调用 generate_repo_health(status=VAR_get_git_status, branches=VAR_get_git_branches, log=VAR_get_git_log)，基于三份数据生成结构化仓库健康报告（评分、工作区分析、分支健康度、提交活跃度、改进建议）。
3. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，可调整参数重新调用；若问题超出工具能力范围或重试耗尽，则继续按后续规则处理。
2. 如果 get_git_status（步骤1并行调用之一）因不在 git 仓库中而失败，标记为 ERROR 并终止，告知用户切换到 git 仓库目录。
3. 如果 get_git_status 返回工作区干净，不影响继续执行——干净的工作区本身就是健康指标之一。
4. 如果 get_git_branches（步骤1并行调用之一）返回空结果或无分支数据，不影响继续执行，报告中标注"分支数据不可用"。
5. 如果 get_git_log（步骤1并行调用之一）因时间范围无提交而返回空结果，报告中标注"近 7 天无提交记录，活跃度低"。
6. 如果 generate_repo_health（步骤2）失败（如 LLM 不可用），将步骤1并行采集的原始数据作为替代报告输出给用户。
7. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
