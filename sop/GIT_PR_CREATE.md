# GIT_PR_CREATE

## Objective
分析当前 feature 分支的变更内容，生成 PR 描述，经用户确认后推送到远程仓库并创建 GitHub Pull Request。

## Description
获取当前分支领先 origin 的提交列表和完整 diff，通过 LLM 生成结构化 PR 描述（标题+概述+变更要点+测试计划）。展示 PR 描述后等待用户确认，确认后推送分支到 origin 并在 GitHub 上创建 Pull Request（base=main）。适用于"准备 PR"、"生成 PR 描述"、"创建 PR"、"推送并发 PR" 等场景。如果用户只想到生成 PR 描述这一步并拒绝推送，INTERRUPT 步骤会终止流程。创建 PR 并在 GitHub 上合并后，可使用 GIT_BRANCH_CLEANUP 清理已合并分支。

## Keywords
GIT, PR, pull-request, description, generate, prepare, push, create, publish, github

## Tools_Required
get_git_commits_ahead, get_git_diff, generate_pr_description, git_push, create_pr

## Retry_Limit
3

## Plan_Steps
1. 同时调用 get_git_commits_ahead() 和 get_git_diff(base="origin/main")，并行采集当前分支领先 origin 的提交列表和相对 main 的累积变更差异。
2. 调用 generate_pr_description(diff=VAR_get_git_diff, commits=VAR_get_git_commits_ahead)，基于变更差异和提交历史生成结构化的 PR 标题、概述、变更要点和测试计划。
3. INTERRUPT。
4. 调用 git_push(branch=从步骤1获取的当前分支名, remote="origin")，将分支推送到远程仓库。如果分支已推送（Everything up-to-date），视为成功继续。
5. 调用 create_pr(data=VAR_generate_pr_description, base="main")，在 GitHub 上创建 Pull Request，目标分支为 main。
6. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，可调整参数重新调用；若问题超出工具能力范围或重试耗尽，则继续按后续规则处理。
2. 如果 get_git_commits_ahead（步骤1并行调用之一）因不在 git 仓库中而失败，标记为 ERROR 并终止，告知用户切换到 git 仓库目录。
3. 如果 get_git_commits_ahead 返回领先提交数为 0（分支与上游完全同步），FINISH 并告知用户：当前分支没有领先 origin 的新提交，无需创建 PR。
4. 如果 get_git_diff 返回空 diff（分支与 main 无代码差异），且步骤1也无领先提交，FINISH 并告知用户无需创建 PR。
5. 如果 generate_pr_description（步骤2）失败（如 LLM 不可用），标记为 ERROR 并终止，告知用户可手动编写 PR 描述后直接使用 gh pr create。
6. 如果用户在 INTERRUPT（步骤3）选择不继续，FINISH 并告知用户 PR 描述已生成但未推送。
7. 如果 git_push（步骤4）因无推送权限或被拒绝而失败，标记为 ERROR 并终止。如果因网络问题失败，可重试一次。
8. 如果 create_pr（步骤5）因 gh CLI 未安装或未认证失败，告知用户：安装 GitHub CLI 并执行 gh auth login。如果因 PR 已存在失败，输出已有 PR 链接并 FINISH。
9. 如果用户要求 draft PR，步骤5 的 create_pr 应传递 draft="true"。
10. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
