# GIT_PR_PREP

## Objective
分析当前 feature 分支的变更内容，自动生成 Pull Request 标题、描述和测试计划。纯只读分析，不推送、不创建 PR。

## Description
获取当前分支领先 origin 的提交列表和完整 diff，通过 LLM 分析变更语义生成结构化的 PR 描述（标题+概述+变更要点+测试计划）。适用于 "准备 PR"、"生成 PR 描述"、"帮我写 PR" 等场景。生成 PR 描述后，用户可自行 review，满意后调用 GIT_PR_CREATE 进行推送和创建。

## Keywords
GIT, PR, pull-request, description, generate, prepare

## Tools_Required
get_git_commits_ahead, get_git_diff, generate_pr_description

## Retry_Limit
3

## Plan_Steps
1. 调用 get_git_commits_ahead()，获取当前分支名和领先 origin 的提交列表。
2. 调用 get_git_diff(staged="false")，获取工作区完整变更差异。
3. 调用 generate_pr_description(diff=VAR_get_git_diff, commits=VAR_get_git_commits_ahead)，基于变更差异和提交历史生成结构化的 PR 标题、概述、变更要点和测试计划。
4. FINISH，将生成的 PR 描述完整输出给用户。提示用户：确认内容无误后，可调用 GIT_PR_CREATE 进行推送并创建 GitHub PR。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，可调整参数重新调用；若问题超出工具能力范围或重试耗尽，则继续按后续规则处理。
2. 如果 get_git_commits_ahead（步骤1）因不在 git 仓库中而失败，标记为 ERROR 并终止，告知用户切换到 git 仓库目录。
3. 如果 get_git_commits_ahead（步骤1）返回领先提交数为 0（分支与上游完全同步），FINISH 并告知用户：当前分支没有领先 origin 的新提交，无需创建 PR。
4. 如果 get_git_diff（步骤2）返回空 diff（工作区干净），不影响继续执行——PR 描述可仅基于已提交但未推送的变更生成。
5. 如果 generate_pr_description（步骤3）失败（如 LLM 不可用），标记为 ERROR 并终止，告知用户可手动编写 PR 描述。
6. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
