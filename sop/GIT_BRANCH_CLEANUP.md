# GIT_BRANCH_CLEANUP

## Objective
扫描本地分支列表，识别已合并且可安全删除的过期分支并清理。

## Description
列出所有本地分支及其合并状态与最后提交日期，分析哪些分支已合并到当前分支且长期未活跃，经过安全判断后删除可清理的分支。适用于用户要求"清理分支"、"删除已合并分支"或"整理仓库分支"的场景。

## Keywords
GIT, branch, cleanup, merged, delete, stale

## Tools_Required
get_git_branches, git_delete_branch

## Retry_Limit
3

## Plan_Steps
1. 调用 get_git_branches()，获取所有本地分支的合并状态和最后提交信息。
2. 如果分支总数不超过3且无已合并的旧分支，就 FINISH 并告知仓库分支干净无需清理。
3. 调用 git_delete_branch(names=从步骤1结果中筛选出的可安全删除分支名，多个用逗号分隔)。删除条件：已合并到当前分支、最后提交距今超过14天。不要删除当前HEAD分支、未合并分支、14天内有提交的活跃分支。
4. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，可调整参数重新调用；若问题超出工具能力范围或重试耗尽，则继续按后续规则处理。
2. 如果 get_git_branches（步骤1）因不在 git 仓库中而失败，标记为 ERROR 并终止，告知用户切换到 git 仓库目录。
3. 如果 get_git_branches（步骤1）返回分支数 <= 3 且无已合并的旧分支，FINISH 并告知用户仓库分支干净无需清理。
4. 如果 git_delete_branch（步骤3）全部失败（如分支未完全合并），列出失败原因并 FINISH，提示用户可手动处理或使用 force=true 强制删除。
5. 如果 git_delete_branch（步骤3）部分成功部分失败，报告成功删除的分支和失败的分支，状态标记为成功（已删除部分）。
6. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
