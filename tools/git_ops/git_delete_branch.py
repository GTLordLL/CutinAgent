import subprocess


def git_delete_branch(names: str, force: str = "false") -> dict:
    """安全删除指定的本地分支（默认仅删除已合并分支）。

    Args:
        names: 要删除的分支名，多个用逗号或空格分隔。
        force: 是否强制删除，"true" 使用 git branch -D，"false"(默认) 使用 git branch -d。
    """
    if not names or not names.strip():
        return {"status": "失败", "summary": "未指定要删除的分支名称。", "detail": ""}

    # 支持逗号和空格分隔
    branch_list = [n.strip() for n in names.replace(',', ' ').split() if n.strip()]
    if not branch_list:
        return {"status": "失败", "summary": "未提取到有效的分支名称。", "detail": ""}

    # 获取当前分支名，防止误删
    try:
        current_branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.STDOUT, universal_newlines=True
        ).strip()
    except subprocess.CalledProcessError as e:
        return {"status": "失败", "summary": f"无法获取当前分支: {e.output.strip()}", "detail": ""}
    except FileNotFoundError:
        return {"status": "失败", "summary": "未找到 git 命令，请确认当前目录是 git 仓库。", "detail": ""}

    # 检查是否包含当前分支
    if current_branch in branch_list:
        return {
            "status": "失败",
            "summary": f"不能删除当前所在分支 '{current_branch}'。请先切换到其他分支后再试。",
            "detail": f"当前分支: {current_branch}\n尝试删除: {', '.join(branch_list)}",
        }

    flag = "-D" if force.lower() == "true" else "-d"
    deleted = []
    failed = []

    for name in branch_list:
        try:
            output = subprocess.check_output(
                ["git", "branch", flag, name],
                stderr=subprocess.STDOUT, universal_newlines=True
            )
            deleted.append(name)
        except subprocess.CalledProcessError as e:
            err_msg = e.output.strip()
            if "not fully merged" in err_msg:
                failed.append(f"{name}: 未完全合并，无法安全删除。如需强制删除请设置 force=true")
            elif "not found" in err_msg:
                failed.append(f"{name}: 分支不存在")
            else:
                failed.append(f"{name}: {err_msg}")

    # 组装结论
    parts = []
    if deleted:
        parts.append(f"成功删除 {len(deleted)} 个分支: {', '.join(deleted)}")
    if failed:
        parts.append(f"{len(failed)} 个失败: {'; '.join(failed)}")

    summary_text = "。".join(parts) if parts else "无操作"
    success = len(deleted) > 0 and len(failed) == 0

    return {
        "status": "成功" if success or (deleted and not failed) else "失败",
        "summary": summary_text,
        "detail": "\n".join(
            [f"[OK] {d}" for d in deleted] +
            [f"[FAIL] {f}" for f in failed]
        ) if (deleted or failed) else "无操作",
    }
