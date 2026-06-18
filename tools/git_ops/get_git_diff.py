import subprocess


def get_git_diff(staged: str = "false", base: str = "") -> dict:
    """获取 Git 代码变更差异。支持工作区 diff 和分支累积 diff 两种模式。

    Args:
        staged: 是否只获取已暂存变更，"true"/"false"，默认 false。base 不为空时忽略此参数。
        base: 对比基线（如 origin/main），执行 git diff <base>...HEAD 获取分支累积差异。
              留空则获取工作区 diff（git diff 或 git diff --staged）。
    """
    try:
        # ── 1. 确定 diff 模式 ──
        if base:
            # 分支累积 diff：git diff <base>...HEAD
            # 三点语法 = 从 merge-base 到 HEAD 的变更，即 PR 包含的全部 diff
            cmd_diff = ["git", "diff", f"{base}...HEAD"]
            cmd_stat = ["git", "diff", "--stat", f"{base}...HEAD"]
            scope = f"分支相对 {base}"
        elif staged.lower() == "true":
            cmd_diff = ["git", "diff", "--staged"]
            cmd_stat = ["git", "diff", "--stat", "--staged"]
            scope = "已暂存"
        else:
            cmd_diff = ["git", "diff"]
            cmd_stat = ["git", "diff", "--stat"]
            scope = "未暂存"

        # ── 2. 获取统计信息 ──
        try:
            stat_output = subprocess.check_output(
                cmd_stat, stderr=subprocess.STDOUT, universal_newlines=True
            ).strip()
        except subprocess.CalledProcessError:
            stat_output = ""

        # ── 3. 获取完整 diff ──
        diff_output = subprocess.check_output(
            cmd_diff, stderr=subprocess.STDOUT, universal_newlines=True
        )

        if not diff_output.strip():
            if base:
                summary_text = f"分支相对 {base} 无代码差异（已同步）。"
            else:
                summary_text = f"工作区无{scope}的变更。"
            return {
                "status": "成功",
                "summary": summary_text,
                "detail": "",
            }

        # ── 4. 解析文件数 ──
        file_count = sum(1 for l in diff_output.split('\n') if l.startswith('diff --git'))
        lines = diff_output.split('\n')
        line_count = len(lines)

        # ── 5. 截断控制 ──
        detail = diff_output.strip()
        if line_count > 200:
            detail = '\n'.join(lines[:200]) + (
                f"\n... (截断，共 {line_count} 行，涉及 {file_count} 个文件)"
            )

        # ── 6. 组装输出：summary=轻量统计，detail=完整diff ──
        if base:
            summary = stat_output if stat_output else f"{file_count} 个文件变更，共 {line_count} 行"
        else:
            summary = f"共 {line_count} 行差异，涉及 {file_count} 个文件"

        summary_text = f"{file_count} 个文件有变更（{scope}）"

        return {
            "status": "成功",
            "summary": summary_text,
            "detail": detail,
        }

    except subprocess.CalledProcessError as e:
        err = e.output.strip() if e.output else str(e)
        return {
            "status": "失败",
            "summary": f"git diff 执行出错: {err}",
            "detail": "",
        }
    except FileNotFoundError:
        return {
            "status": "失败",
            "summary": "未找到 git 命令，请确认当前目录是 git 仓库。",
            "detail": "",
        }
    except Exception as e:
        return {
            "status": "失败",
            "summary": f"获取变更差异异常: {str(e)}",
            "detail": "",
        }
