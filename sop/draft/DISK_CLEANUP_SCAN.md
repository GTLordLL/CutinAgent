# DISK_CLEANUP_SCAN

## Objective
扫描指定目录中的大文件，识别可清理的候选文件。

## Description
在用户指定的目录中查找占用磁盘空间最大的文件，并建议对哪些文件进行删除或归档处理。

## Keywords
DISK, find, large-file, cleanup, storage, du, space, directory

## Tools_Required
locate_large_files, check_file_access, generate_summary_report

## Retry_Limit
3

## Plan_Steps
1. 调用 locate_large_files(path=用户指定的目录路径, limit=5)，找出该目录下占用磁盘空间最大的前5个文件，并且总结成大文件列表写在这一步后面供第二步遍历。
2. 基于步骤1的大文件列表，同时为其中每一个大文件调用 check_file_access(path=该文件的完整路径)，验证其权限、所有者和是否可安全删除。
3. 调用 generate_summary_report(data=前面所有步骤采集的大文件列表和权限数据)，汇总所有数据生成按文件大小排序的清理候选清单。清单需标注每个文件的大小和路径、是否可以安全删除、是否需要提升权限。
4. FINISH。

## Global_Exception_Handling
1. 当任何步骤返回了出乎意料的结果且可归因于参数填写错误时，SOP Execution Scheduler 可在 Retry_Limit 内调整参数重试；若问题超出工具能力范围（参考 AVAILABLE_TOOLS 中的 param_desc）或重试耗尽，则继续按后续规则处理。
2. 如果 locate_large_files（步骤1）失败（如目录不存在或权限不足），标记为 ERROR 并终止，告知用户检查目录路径和访问权限。
3. 如果 locate_large_files（步骤1）成功但返回空列表，直接跳至步骤4，FINISH 并告知用户"指定目录未发现大文件，无需清理"。
4. 如果 check_file_access（步骤2）返回的结果不符合预期，按规则1重试；若全部文件均重试耗尽，标记为 ERROR 并终止。
5. 如果 generate_summary_report（步骤3）失败，输出步骤1和步骤2已采集的原始大文件列表和权限数据作为替代报告。
6. 如果连续2个步骤的工具均返回失败，标记为 ERROR 并终止。
