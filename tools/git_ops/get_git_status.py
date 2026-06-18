import subprocess


def get_git_status() -> dict:
    """获取 Git 工作区状态：分支名 + 变更文件计数。"""
    try:
        branch = subprocess.check_output(
            ["git", "branch", "--show-current"],
            stderr=subprocess.STDOUT, universal_newlines=True
        ).strip()

        porcelain = subprocess.check_output(
            ["git", "status", "--porcelain"],
            stderr=subprocess.STDOUT, universal_newlines=True
        )

        if not porcelain.strip():
            return {
                "status": "成功",
                "summary": f"分支 '{branch}' 工作区干净，没有待提交的变更。",
                "detail": "",
            }

        lines = porcelain.strip().split('\n')
        staged = sum(1 for l in lines if l[0] != ' ' and l[1] != '?')
        modified = sum(1 for l in lines if l[0] != 'M' and l[1] == 'M')
        untracked = sum(1 for l in lines if l.startswith('??'))
        deleted = sum(1 for l in lines if l.startswith(' D') or l.startswith('D '))

        return {
            "status": "成功",
            "summary": f"分支 '{branch}' 有未提交变更",
            "detail": porcelain.strip(),
        }

    except subprocess.CalledProcessError as e:
        return {"status": "失败", "summary": f"git status 执行出错: {e.output.strip()}", "detail": ""}
    except FileNotFoundError:
        return {"status": "失败", "summary": "未找到 git 命令，请确认当前目录是 git 仓库。", "detail": ""}
    except Exception as e:
        return {"status": "失败", "summary": f"获取工作区状态异常: {str(e)}", "detail": ""}
