import subprocess


def get_git_log(since: str = "today", author: str = "", limit: int = 50) -> dict:
    """获取 Git 提交历史记录，支持 today/yesterday/Ndays 时间过滤。"""
    try:
        limit = min(max(int(limit), 1), 100)

        cmd = [
            "git", "log",
            f"--max-count={limit}",
            "--format=%h %ad %an: %s",
            "--date=short"
        ]

        if since == "today":
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

        if not output.strip():
            return {
                "status": "成功",
                "conclusion": f"在 '{since}' 时间范围内未找到提交记录。",
                "summary": "",
                "detail": "",
            }

        lines = output.strip().split('\n')
        return {
            "status": "成功",
            "conclusion": f"在 '{since}' 范围内找到 {len(lines)} 条提交",
            "summary": f"{len(lines)} 条提交记录",
            "detail": output.strip(),
        }

    except subprocess.CalledProcessError as e:
        return {"status": "失败", "conclusion": f"git log 执行出错: {e.output.strip()}", "summary": "", "detail": ""}
    except FileNotFoundError:
        return {"status": "失败", "conclusion": "未找到 git 命令，请确认当前目录是 git 仓库。", "summary": "", "detail": ""}
    except Exception as e:
        return {"status": "失败", "conclusion": f"获取提交日志异常: {str(e)}", "summary": "", "detail": ""}
