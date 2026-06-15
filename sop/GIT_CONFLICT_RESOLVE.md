# GIT_CONFLICT_RESOLVE

## Objective
检测 Git merge/rebase 冲突，提取冲突标记内容，通过 LLM 分析两侧代码意图并给出解决方案建议。

## Description
当用户在 merge 或 rebase 过程中遇到冲突时，检测所有冲突文件并提取 `<<<<<<<` / `=======` / `>>>>>>>` 标记区域，调用 LLM 分析每个冲突的两侧意图、冲突根因，并针对每个冲突区域推荐 `keep-ours` / `keep-theirs` / `merge-both` / `rewrite` 策略及合并后代码。适用于用户说"解决冲突"、"分析冲突"、"帮我看看这个冲突怎么改"等场景。

## Keywords
GIT, conflict, merge, rebase, resolve, diff, analyze

## Tools_Required
get_git_conflicts, generate_conflict_resolution

## Retry_Limit
2

## Plan_Steps
1. 调用 get_git_conflicts() 检测当前仓库是否存在冲突文件。
2. 如果步骤1返回无冲突（0个冲突文件），FINISH 并告知用户仓库当前无合并冲突。
3. 调用 generate_conflict_resolution(data=VAR_get_git_conflicts) 分析冲突并生成解决方案建议。
4. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，可调整参数重新调用；若问题超出工具能力范围或重试耗尽，则继续按后续规则处理。
2. 如果 get_git_conflicts（步骤1）因不在 git 仓库中而失败，标记为 ERROR 并终止，告知用户切换到 git 仓库目录。
3. 如果 get_git_conflicts（步骤1）返回无冲突，FINISH 并告知用户仓库干净。
4. 如果 generate_conflict_resolution（步骤3）因 LLM 不可用而失败，回退方案：直接输出 get_git_conflicts 的原始冲突内容，告知用户 LLM 暂不可用但冲突标记已列出，用户可自行判断。
5. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
