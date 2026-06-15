import subprocess
import os


def get_git_conflicts(base: str = "", theirs: str = "") -> dict:
    """列出所有冲突文件及冲突标记内容。

    纯只读操作，不修改任何文件。
    支持 rebase (base/theirs 反向) 和 merge 两种场景。

    Args:
        base: rebase 场景下的上游分支 (可选)。
        theirs: rebase 场景下的目标分支 (可选)。
    """
    try:
        # ── 1. 列出冲突文件 ──
        result = subprocess.run(
            ["git", "diff", "--name-only", "--diff-filter=U"],
            capture_output=True, text=True, check=True
        )
        conflicted_files = [f.strip() for f in result.stdout.strip().split('\n') if f.strip()]

        if not conflicted_files:
            return {
                "status": "成功",
                "conclusion": "仓库当前无合并冲突，工作区干净。",
                "summary": "0 个冲突文件",
                "detail": "git diff --name-only --diff-filter=U 返回空。",
            }

        # ── 2. 获取合并/变基上下文 ──
        context_lines = []
        context_lines.append(f"工作目录: {os.getcwd()}")

        # 检测是否在 merge 中
        merge_head = ""
        if os.path.exists(".git/MERGE_HEAD"):
            try:
                mh = subprocess.run(
                    ["git", "log", "-1", "--format=%h %s (%an, %ar)", "MERGE_HEAD"],
                    capture_output=True, text=True, check=True
                )
                merge_head = mh.stdout.strip()
                context_lines.append(f"MERGE_HEAD (待合入分支): {merge_head}")
            except subprocess.CalledProcessError:
                pass

        if os.path.exists(".git/MERGE_MSG"):
            try:
                with open(".git/MERGE_MSG", "r", encoding="utf-8") as f:
                    merge_msg = f.read().strip()
                context_lines.append(f"MERGE_MSG: {merge_msg}")
            except Exception:
                pass

        # 检测是否在 rebase 中
        if os.path.exists(".git/rebase-merge") or os.path.exists(".git/rebase-apply"):
            context_lines.append("状态: 正在进行 rebase 操作")
            if base:
                context_lines.append(f"  base (上游): {base}")
            if theirs:
                context_lines.append(f"  theirs (目标): {theirs}")

        # ── 3. 获取冲突状态摘要 ──
        status_result = subprocess.run(
            ["git", "status", "--porcelain"],
            capture_output=True, text=True, check=True
        )
        conflict_status_lines = [
            l for l in status_result.stdout.strip().split('\n')
            if l.strip() and ('U' in l[:2] or l[:2] in ('AA', 'DD', 'AU', 'UA', 'DU', 'UD'))
        ]
        if conflict_status_lines:
            context_lines.append(f"\n冲突状态 ({len(conflict_status_lines)} 条):")
            for l in conflict_status_lines:
                context_lines.append(f"  {l}")

        # ── 4. 提取每个冲突文件的冲突内容 ──
        lines = []
        lines.append(f"=== 冲突文件 ({len(conflicted_files)} 个) ===")
        lines.extend(context_lines)
        lines.append("")

        for fpath in conflicted_files:
            lines.append(f"--- 文件: {fpath} ---")
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    content = f.read()
                conflict_sections = _extract_conflicts(content)
                if conflict_sections:
                    for i, section in enumerate(conflict_sections, 1):
                        lines.append(f"\n[冲突区域 {i}]")
                        lines.append(section)
                else:
                    # 文件标记为冲突但无标准冲突标记——可能是二进制或特殊冲突
                    lines.append("(无标准冲突标记，可能是二进制文件或内容冲突)")
                    lines.append(f"文件大小: {len(content)} 字节")
            except UnicodeDecodeError:
                lines.append("(二进制文件，无法显示内容)")
            except Exception as e:
                lines.append(f"(读取失败: {e})")
            lines.append("")

        detail = "\n".join(lines)

        return {
            "status": "成功",
            "conclusion": f"检测到 {len(conflicted_files)} 个冲突文件: {', '.join(conflicted_files)}",
            "summary": f"冲突文件({len(conflicted_files)}): {', '.join(conflicted_files)}",
            "detail": detail,
        }

    except subprocess.CalledProcessError as e:
        return {
            "status": "失败",
            "conclusion": f"git 命令执行失败: {e.stderr.strip() if e.stderr else str(e)}",
            "summary": "",
            "detail": "",
        }
    except FileNotFoundError:
        return {
            "status": "失败",
            "conclusion": "未找到 git 命令，请确认当前目录是 git 仓库。",
            "summary": "",
            "detail": "",
        }
    except Exception as e:
        return {
            "status": "失败",
            "conclusion": f"获取冲突信息异常: {str(e)}",
            "summary": "",
            "detail": "",
        }


def _extract_conflicts(content: str) -> list[str]:
    """从文件内容中提取所有 <<<<<<< ... >>>>>>> 冲突区域。"""
    sections = []
    in_conflict = False
    current = []

    for line in content.split('\n'):
        if line.startswith('<<<<<<<'):
            in_conflict = True
            current = [line]
        elif line.startswith('>>>>>>>') and in_conflict:
            current.append(line)
            sections.append('\n'.join(current))
            in_conflict = False
            current = []
        elif in_conflict:
            current.append(line)

    # 处理未闭合的冲突标记（文件截断等异常情况）
    if in_conflict and current:
        current.append(">>>>>>> (文件截断，冲突标记未闭合)")
        sections.append('\n'.join(current))

    return sections
