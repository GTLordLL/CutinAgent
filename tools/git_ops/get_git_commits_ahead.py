import subprocess


def get_git_commits_ahead(remote: str = "origin") -> dict:
    """获取当前分支领先远程的提交列表。

    Args:
        remote: 远程名称，默认 origin。
    """
    try:
        # ── 1. 获取当前分支名 ──
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.STDOUT, universal_newlines=True
        ).strip()

        if not branch:
            return {"status": "失败", "summary": "当前处于 detached HEAD 状态，无法确定分支。", "detail": ""}

        # ── 2. 查找对比基线：upstream → remote/branch → remote/HEAD ──
        upstream = ""
        try:
            upstream = subprocess.check_output(
                ["git", "rev-parse", "--abbrev-ref", f"{branch}@{{upstream}}"],
                stderr=subprocess.STDOUT, universal_newlines=True
            ).strip()
        except subprocess.CalledProcessError:
            pass

        if not upstream:
            # 尝试 remote/branch（已推送但未设 upstream 的分支）
            candidate = f"{remote}/{branch}"
            try:
                subprocess.check_output(
                    ["git", "rev-parse", "--verify", candidate],
                    stderr=subprocess.STDOUT, universal_newlines=True
                )
                upstream = candidate
            except subprocess.CalledProcessError:
                pass

        # 仍未找到：分支未推送，回退到远程默认分支作为对比基线
        base_ref = ""
        if not upstream:
            for default_name in ("main", "master"):
                candidate = f"{remote}/{default_name}"
                try:
                    subprocess.check_output(
                        ["git", "rev-parse", "--verify", candidate],
                        stderr=subprocess.STDOUT, universal_newlines=True
                    )
                    base_ref = candidate
                    break
                except subprocess.CalledProcessError:
                    continue

            if not base_ref:
                return {
                    "status": "成功",
                    "summary": f"分支: {branch}（未推送，无对比基线）",
                    "detail": f"当前分支: {branch}\n远程: {remote}\n对比基线: 无\n\n（分支未推送，且远程无默认分支可对比）",
                }

            # 使用远程默认分支作为基线（commits from base_ref to HEAD）
            upstream = base_ref
            is_new_branch = True
        else:
            is_new_branch = False

        # ── 3. 获取领先的提交（oneline 摘要） ──
        try:
            log_oneline = subprocess.check_output(
                ["git", "log", f"{upstream}..HEAD", "--oneline", "--no-merges"],
                stderr=subprocess.STDOUT, universal_newlines=True
            ).strip()
        except subprocess.CalledProcessError:
            log_oneline = ""

        if not log_oneline:
            # 检查是否有 merge commits
            try:
                log_oneline = subprocess.check_output(
                    ["git", "log", f"{upstream}..HEAD", "--oneline"],
                    stderr=subprocess.STDOUT, universal_newlines=True
                ).strip()
            except subprocess.CalledProcessError:
                log_oneline = ""

        commits = [l for l in log_oneline.split('\n') if l.strip()] if log_oneline else []
        ahead_count = len(commits)

        # ── 4. 获取完整提交信息（用于 PR 描述生成） ──
        try:
            log_full = subprocess.check_output(
                ["git", "log", f"{upstream}..HEAD",
                 "--format=commit %h%nAuthor: %an <%ae>%nDate: %ad%n%n    %s%n%n    %b%n---"],
                stderr=subprocess.STDOUT, universal_newlines=True
            ).strip()
        except subprocess.CalledProcessError:
            log_full = ""

        # ── 5. 组装输出 ──
        detail_lines = [
            f"当前分支: {branch}",
            f"远程: {remote}",
            f"上游引用: {upstream if upstream else '无（新分支，尚未推送）'}",
            f"领先提交数: {ahead_count}",
            "",
        ]
        if commits:
            detail_lines.append("--- 领先提交 ---")
            for c in commits:
                detail_lines.append(c)
            detail_lines.append("")
            if log_full:
                detail_lines.append("--- 完整提交信息 ---")
                detail_lines.append(log_full)
        else:
            detail_lines.append("（无领先提交，分支与上游同步）")

        # summary: 紧凑格式，列出分支+提交摘要
        if ahead_count == 0:
            summary = f"分支: {branch}，领先提交: 0（与 {upstream} 同步）"
        elif is_new_branch:
            summary = f"分支: {branch}（新分支），共{ahead_count}个提交: " + " | ".join(commits[:10])
            if ahead_count > 10:
                summary += f" ... 及其他{ahead_count - 10}条"
        else:
            summary = f"分支: {branch}，领先 {upstream} 共{ahead_count}个提交: " + " | ".join(commits[:10])
            if ahead_count > 10:
                summary += f" ... 及其他{ahead_count - 10}条"

        return {
            "status": "成功",
            "summary": summary,
            "detail": "\n".join(detail_lines),
        }

    except subprocess.CalledProcessError as e:
        return {"status": "失败", "summary": f"git log 执行出错: {e.output.strip()}", "detail": ""}
    except FileNotFoundError:
        return {"status": "失败", "summary": "未找到 git 命令，请确认当前目录是 git 仓库。", "detail": ""}
    except Exception as e:
        return {"status": "失败", "summary": f"获取领先提交异常: {str(e)}", "detail": ""}
