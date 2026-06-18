import subprocess


def git_push(branch: str = "", remote: str = "origin", set_upstream: str = "false",
             force: str = "false") -> dict:
    """推送当前分支到远程仓库。

    Args:
        branch: 要推送的分支名，留空自动检测当前分支。
        remote: 远程名称，默认 origin。
        set_upstream: 是否设置上游跟踪 (-u)，"true"/"false"，默认 false。
        force: 是否强制推送，"true"/"false"，默认 false。
    """
    try:
        # ── 1. 获取当前分支（若未指定） ──
        if not branch:
            branch = subprocess.check_output(
                ["git", "branch", "--show-current"],
                stderr=subprocess.STDOUT, universal_newlines=True
            ).strip()

        if not branch:
            return {"status": "失败", "summary": "当前处于 detached HEAD 状态，无法推送。", "detail": ""}

        # ── 2. 检查 remote 是否存在 ──
        try:
            remotes = subprocess.check_output(
                ["git", "remote"],
                stderr=subprocess.STDOUT, universal_newlines=True
            ).strip()
            if remote not in remotes.split('\n'):
                return {
                    "status": "失败",
                    "summary": f"远程 '{remote}' 不存在。可用远程: {remotes}",
                    "detail": "",
                }
        except subprocess.CalledProcessError:
            return {"status": "失败", "summary": "未配置任何远程仓库。", "detail": ""}

        # ── 3. 构建 push 命令 ──
        cmd = ["git", "push"]

        if set_upstream.lower() == "true":
            cmd.append("--set-upstream")

        if force.lower() == "true":
            cmd.append("--force-with-lease")  # 比 --force 更安全

        cmd.extend([remote, branch])

        # ── 4. 执行推送 ──
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, universal_newlines=True
        )

        # ── 5. 解析输出 ──
        output_stripped = output.strip()
        summary = output_stripped.replace('\n', ' | ')

        return {
            "status": "成功",
            "summary": summary,
            "detail": output_stripped,
        }

    except subprocess.CalledProcessError as e:
        err = e.output.strip() if e.output else str(e)
        hint = ""
        if "rejected" in err.lower():
            hint = "（提示：远程有更新，先 git pull 或使用 force=true 强制推送）"
        elif "no upstream" in err.lower() or "set-upstream" in err.lower():
            hint = "（提示：使用 set_upstream=true 设置上游跟踪）"
        return {
            "status": "失败",
            "summary": f"推送失败: {err}{hint}",
            "detail": err,
        }
    except FileNotFoundError:
        return {"status": "失败", "summary": "未找到 git 命令，请确认当前目录是 git 仓库。", "detail": ""}
    except Exception as e:
        return {"status": "失败", "summary": f"推送过程异常: {str(e)}", "detail": ""}
