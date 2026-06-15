# GIT_RELEASE_NOTES

## Objective
读取两个 Git tag（或指定版本范围）之间的所有提交记录，通过 LLM 按 feat/fix/refactor 等类型分组生成结构化的 Release Notes / Changelog。

## Description
通过 git log 获取版本 tag 间的提交历史（如 v0.1.0..v0.2.0），调用 LLM 将提交按 conventional commit 前缀分类聚合（新功能/修复/重构/文档/杂项），生成面向用户的结构化 changelog。纯只读，零风险。适用于用户要求"生成 Release Notes"、"写 changelog"或"这个版本改了什么"的场景。

## Keywords
GIT, release-notes, changelog, tag, version, release, log, generate

## Tools_Required
get_git_log, generate_release_notes

## Retry_Limit
3

## Plan_Steps
1. 调用 get_git_log(from_tag=VAR_from_tag, to_tag=VAR_to_tag, limit=100)，获取两个版本标签之间的所有提交记录。from_tag 和 to_tag 由用户在指令中指定（如 "v0.1.0" 到 "v0.2.0"），如果用户只给了一个 tag 则 to_tag 默认 "HEAD"。如果用户没有指定任何 tag，则 from_tag 为最后一个 tag、to_tag 为 HEAD。
2. 调用 generate_release_notes(data=VAR_get_git_log)，基于提交历史按 feat/fix/refactor/docs/chore/test 分组，生成结构化的 Release Notes markdown。
3. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，可调整参数重新调用；若问题超出工具能力范围或重试耗尽，则继续按后续规则处理。
2. 如果 get_git_log（步骤1）因不在 git 仓库中而失败，标记为 ERROR 并终止，告知用户切换到 git 仓库目录。
3. 如果 get_git_log（步骤1）返回空结果（tag 间无提交），FINISH 并告知用户该版本范围内无提交记录。
4. 如果 generate_release_notes（步骤2）失败（如 LLM 不可用），将步骤1的原始提交列表作为替代输出给用户，标注"LLM 不可用，以下是原始提交记录"。
5. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
