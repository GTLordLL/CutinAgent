import subprocess


def get_git_diff(staged: bool = False) -> dict:
    """获取 Git 工作区代码变更差异，超过 200 行截断。"""
    try:
        cmd = ["git", "diff"]
        if staged:
            cmd.append("--staged")

        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, universal_newlines=True
        )

        if not output.strip():
            scope = "已暂存" if staged else "未暂存"
            return {
                "status": "成功",
                "conclusion": f"工作区无{scope}的变更。",
                "summary": "",
                "detail": "",
            }

        lines = output.split('\n')
        line_count = len(lines)
        file_count = sum(1 for l in lines if l.startswith('diff --git'))

        if line_count > 200:
            output = '\n'.join(lines[:200]) + (
                f"\n... (截断，共 {line_count} 行，涉及 {file_count} 个文件)"
            )

        return {
            "status": "成功",
            "conclusion": f"{file_count} 个文件有变更",
            "summary": f"共 {line_count} 行差异，涉及 {file_count} 个文件",
            "detail": output.strip(),
        }

    except subprocess.CalledProcessError as e:
        return {"status": "失败", "conclusion": f"git diff 执行出错: {e.output.strip()}", "summary": "", "detail": ""}
    except FileNotFoundError:
        return {"status": "失败", "conclusion": "未找到 git 命令，请确认当前目录是 git 仓库。", "summary": "", "detail": ""}
    except Exception as e:
        return {"status": "失败", "conclusion": f"获取变更差异异常: {str(e)}", "summary": "", "detail": ""}
