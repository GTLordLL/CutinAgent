# GIT_PR_PREP

## Objective
分析当前分支的变更内容，自动生成 Pull Request 标题、描述和测试计划，可选推送到远程仓库。

## Description
获取当前分支领先 origin 的提交列表和完整 diff，通过 LLM 分析变更语义生成结构化的 PR 描述（标题+概述+变更要点+测试计划）。适用于用户完成代码后要求"创建 PR"、"生成 PR 描述"或"推送分支"的场景。

## Keywords
GIT, PR, pull-request, push, description, generate, remote

## Tools_Required
get_git_commits_ahead, get_git_diff, generate_pr_description, git_push

## Retry_Limit
3

## Plan_Steps
1. 调用 get_git_commits_ahead()，获取当前分支名和领先 origin 的提交列表。
2. 调用 get_git_diff(staged="false")，获取工作区完整变更差异。
3. 调用 generate_pr_description(diff=VAR_get_git_diff, commits=VAR_get_git_commits_ahead)，基于变更差异和提交历史生成结构化的 PR 标题、概述、变更要点和测试计划。
4. 根据用户指令判断是否需要推送：如果用户明确要求推送（如"推送"、"push"、"创建PR并推送"），调用 git_push(branch=从步骤1获取的当前分支名, remote="origin") 推送到远程仓库；如果用户只要求生成描述（如"生成PR描述"），跳过推送，FINISH 并输出生成的PR描述。
5. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，可调整参数重新调用；若问题超出工具能力范围或重试耗尽，则继续按后续规则处理。
2. 如果 get_git_commits_ahead（步骤1）因不在 git 仓库中而失败，标记为 ERROR 并终止，告知用户切换到 git 仓库目录。
3. 如果 get_git_commits_ahead（步骤1）返回领先提交数为 0（分支与上游同步），FINISH 并告知用户当前分支没有需要创建 PR 的新提交。
4. 如果 get_git_diff（步骤2）返回空 diff（工作区干净），不影响继续执行——PR 可能仅包含已提交但未推送的变更。
5. 如果 generate_pr_description（步骤3）失败（如 LLM 不可用），告知用户并 FINISH，提示可手动编写 PR 描述。
6. 如果 git_push（步骤4）失败（如无推送权限、rejected），报告失败原因并 FINISH，但 PR 描述已生成，用户可手动推送。
7. 如果用户指令中明确包含"推送"或"push"关键词，步骤4应执行 git_push；否则步骤4应跳过推送直接 FINISH。
8. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
