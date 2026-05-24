# GIT_SMART_COMMIT

## Objective
扫描 Git 工作区变更，自动生成 conventional commit message 并提交。

## Description
检查当前分支的未暂存变更，通过 LLM 分析 diff 内容生成高质量的 commit message，然后暂存文件并执行 git commit。适用于用户要求"帮我提交代码"或"生成 commit message"的场景。

## Keywords
GIT, commit, stage, add, conventional-commits, message

## Tools_Required
get_git_status, get_git_diff, generate_commit_message, git_commit

## Retry_Limit
3

## Plan_Steps
1. 同时调用 get_git_status() 和 get_git_diff(staged=False)，并行采集工作区状态概览和代码变更详情。
2. 调用 generate_commit_message(data=VAR_get_git_diff)，基于变更差异生成一条遵循conventional commits规范的commit message。
3. 调用 git_commit(message=步骤2生成的commit message, files=用户指定或'.')，暂存文件并提交。如果用户未指定文件范围，默认提交所有变更（files='.'）。
4. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，可调整参数重新调用；若问题超出工具能力范围或重试耗尽，则继续按后续规则处理。
2. 如果 get_git_status 或 get_git_diff（步骤1）因不在 git 仓库中而失败，标记为 ERROR 并终止，告知用户切换到 git 仓库目录。
3. 如果 get_git_status 返回工作区干净（无变更），FINISH 并告知用户无需提交。
4. 如果 generate_commit_message（步骤2）失败，标记为 ERROR 并终止，告知用户 commit message 生成失败，可手动提交。
5. 如果 git_commit（步骤3）失败，标记为 ERROR 并终止，输出失败原因并提示用户可用 git reset --soft HEAD~1 回滚（如果提交已部分完成）。
6. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
