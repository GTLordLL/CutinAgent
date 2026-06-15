import subprocess


def get_git_log(since: str = "today", author: str = "",
                limit: int = 50, from_tag: str = "", to_tag: str = "") -> dict:
    """获取 Git 提交历史记录，支持 today/yesterday/Ndays 时间过滤或 tag 范围。

    Args:
        since: 起始时间 today/yesterday/Ndays。
        author: 按作者筛选（可选）。
        limit: 返回条数，默认50，上限100。
        from_tag: 起始 tag（如 v0.1.0），与 to_tag 配合使用，覆盖 since。
        to_tag: 结束 tag/ref（如 HEAD 或 v0.2.0），默认 HEAD。
    """
    try:
        limit = min(max(int(limit), 1), 100)

        cmd = [
            "git", "log",
            f"--max-count={limit}",
            "--format=%h %ad %an: %s",
            "--date=short"
        ]

        # tag range 优先于时间过滤
        if from_tag:
            to_ref = to_tag if to_tag else "HEAD"
            cmd.append(f"{from_tag}..{to_ref}")
        elif since == "today":
            cmd.append("--since=midnight")
        elif since == "yesterday":
            cmd.append("--since=yesterday.midnight")
            cmd.append("--until=midnight")
        elif since.endswith("days"):
            days = since.replace("days", "")
            cmd.append(f"--since={days}.days.ago")
        elif since:
            cmd.append(f"--since={since}")

        if author:
            cmd.append(f"--author={author}")

        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, universal_newlines=True
        )

        if from_tag:
            range_label = f"{from_tag}..{to_tag if to_tag else 'HEAD'}"
        else:
            range_label = f"'{since}'"

        if not output.strip():
            return {
                "status": "成功",
                "conclusion": f"在 {range_label} 范围内未找到提交记录。",
                "summary": "",
                "detail": "",
            }

        lines = output.strip().split('\n')
        # Build compact summary with actual commit info (hash + oneline)
        # Format: %h %ad %an: %s → compact each line to 80 chars max
        show = min(len(lines), 20)
        compact = " | ".join(line[:80] for line in lines[:show])
        summary = f"共{len(lines)}条: {compact}"
        if len(lines) > 20:
            summary += f" ...等{len(lines)}条"
        return {
            "status": "成功",
            "conclusion": f"在 {range_label} 范围内找到 {len(lines)} 条提交",
            "summary": summary,
            "detail": output.strip(),
        }

    except subprocess.CalledProcessError as e:
        return {"status": "失败", "conclusion": f"git log 执行出错: {e.output.strip()}", "summary": "", "detail": ""}
    except FileNotFoundError:
        return {"status": "失败", "conclusion": "未找到 git 命令，请确认当前目录是 git 仓库。", "summary": "", "detail": ""}
    except Exception as e:
        return {"status": "失败", "conclusion": f"获取提交日志异常: {str(e)}", "summary": "", "detail": ""}
