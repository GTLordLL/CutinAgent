import subprocess
import re


def git_commit(message: str, files: str = ".") -> dict:
    """暂存指定文件并提交。第一个写操作工具，失败可用 git reset --soft HEAD~1 回滚。"""
    try:
        status_output = subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.STDOUT, universal_newlines=True
        )
        if not status_output.strip():
            return {
                "status": "失败",
                "conclusion": "工作区干净，没有需要提交的变更。",
                "summary": "",
                "detail": "",
            }

        if files == ".":
            subprocess.check_output(
                ["git", "add", "-A"],
                stderr=subprocess.STDOUT, universal_newlines=True
            )
        else:
            for f in files.split():
                subprocess.check_output(
                    ["git", "add", f],
                    stderr=subprocess.STDOUT, universal_newlines=True
                )

        commit_output = subprocess.check_output(
            ["git", "commit", "-m", message],
            stderr=subprocess.STDOUT, universal_newlines=True
        )

        hash_match = re.search(r'\[[\w\-]+ ([a-f0-9]+)\]', commit_output)
        commit_hash = hash_match.group(1) if hash_match else "unknown"

        changed = re.search(r'(\d+) files? changed', commit_output)
        inserted = re.search(r'(\d+) insertions?', commit_output)
        deleted = re.search(r'(\d+) deletions?', commit_output)
        summary_parts = []
        if changed:
            summary_parts.append(f"{changed.group(1)} 个文件变更")
        if inserted:
            summary_parts.append(f"+{inserted.group(1)} 行")
        if deleted:
            summary_parts.append(f"-{deleted.group(1)} 行")

        summary = ", ".join(summary_parts) if summary_parts else commit_output.strip()

        return {
            "status": "成功",
            "conclusion": f"提交成功 (hash: {commit_hash})",
            "summary": summary,
            "detail": "",
        }

    except subprocess.CalledProcessError as e:
        return {
            "status": "失败",
            "conclusion": f"git commit 执行失败: {e.output.strip()}。提示: 如需回滚，可执行 git reset --soft HEAD~1。",
            "summary": "",
            "detail": "",
        }
    except FileNotFoundError:
        return {"status": "失败", "conclusion": "未找到 git 命令，请确认当前目录是 git 仓库。", "summary": "", "detail": ""}
    except Exception as e:
        return {"status": "失败", "conclusion": f"提交过程异常: {str(e)}", "summary": "", "detail": ""}
