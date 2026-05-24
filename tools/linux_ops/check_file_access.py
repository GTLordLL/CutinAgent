import os
import pwd
import grp
import stat

def check_file_access(path: str):
    """
    专家级权限与所有权诊断工具
    """
    try:
        # 1. 基础存在性检查
        if not os.path.exists(path):
            return f"失败 | 路径 {path} 不存在，无法检查权限。"

        # 2. 获取文件详细属性
        file_stat = os.stat(path)
        mode = file_stat.st_mode
        
        # 转换权限位为易读格式 (例如: 644, 755)
        oct_perms = oct(mode)[-3:]
        # 转换所有者与所属组 ID 为名称
        owner_name = pwd.getpwuid(file_stat.st_uid).pw_name
        group_name = grp.getgrgid(file_stat.st_gid).gr_name

        # 3. 获取当前 Agent 进程的运行身份
        current_user = pwd.getpwuid(os.getuid()).pw_name
        current_groups = [grp.getgrgid(g).gr_name for g in os.getgroups()]

        # 4. 专家权限判定逻辑
        is_dir = stat.S_ISDIR(mode)
        readable = os.access(path, os.R_OK)
        writable = os.access(path, os.W_OK)
        executable = os.access(path, os.X_OK)

        access_summary = []
        if readable: access_summary.append("可读")
        if writable: access_summary.append("可写")
        if executable: access_summary.append("可执行" if not is_dir else "可进入")

        # 5. 生成专家结论
        status_prefix = "成功 | [权限诊断]"
        identity_info = f"当前 Agent 身份: {current_user} (所属组: {', '.join(current_groups)})"
        file_info = f"目标 {'目录' if is_dir else '文件'} 所有者: {owner_name}:{group_name}, 权限位: {oct_perms}"
        
        # 核心定性结论
        if not readable:
            conclusion = f"由于当前用户 {current_user} 不在 {owner_name} 的权限范围内且没有读权限，导致访问受限。请考虑使用 sudo 或修改文件归属。"
        elif not writable and "写" in access_summary:
            conclusion = "虽然有读权限，但缺乏写权限，无法修改文件。"
        else:
            conclusion = f"当前权限状态为 ({', '.join(access_summary)})，状态符合预期。"

        return (
            f"{status_prefix} 结论: {conclusion}\n"
            f"[DETAIL]\n"
            f"详情: {file_info}\n"
            f"环境: {identity_info}"
        )

    except Exception as e:
        return f"失败 | 权限诊断过程崩溃: {str(e)}"