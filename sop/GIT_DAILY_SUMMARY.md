# GIT_DAILY_SUMMARY

## Objective
汇总今日所有 Git 提交记录，按类型分类生成结构化的变更日报。

## Description
读取今日的 git log，通过 LLM 将提交按 feat/fix/refactor/docs 等类型分类汇总，生成一份简洁的开发日报。适用于用户要求"写日报"、"今天做了什么"或"汇总今日提交"的场景。

## Keywords
GIT, log, daily, summary, report, changelog

## Tools_Required
get_git_log, generate_daily_report

## Retry_Limit
3

## Plan_Steps
1. 调用 get_git_log(since=today, limit=50)，获取今日所有提交记录（hash、日期、作者、message）。
2. 调用 generate_daily_report(data=VAR_get_git_log)，将今日提交按类型分类汇总生成结构化日报。
3. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，可调整参数重新调用；若问题超出工具能力范围或重试耗尽，则继续按后续规则处理。
2. 如果 get_git_log（步骤1）因不在 git 仓库中而失败，标记为 ERROR 并终止，告知用户切换到 git 仓库目录。
3. 如果 get_git_log（步骤1）返回空结果（今日无提交），FINISH 并告知用户今日暂无代码提交。
4. 如果 generate_daily_report（步骤2）失败，输出步骤1的原始 git log 数据作为替代结果。
5. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
