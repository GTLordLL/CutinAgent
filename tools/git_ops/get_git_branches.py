import subprocess


def get_git_branches(remote: str = "false") -> dict:
    """列出所有本地分支及其合并状态、最后提交信息。

    Args:
        remote: 是否包含远程分支，"true" 包含，"false"(默认) 仅本地。
    """
    try:
        # ── 1. 获取已合并到当前分支的分支名集合 ──
        try:
            merged_raw = subprocess.check_output(
                ["git", "branch", "--merged"],
                stderr=subprocess.STDOUT, universal_newlines=True
            )
            merged_set = {
                line.strip().lstrip("* ") for line in merged_raw.strip().split('\n') if line.strip()
            }
        except subprocess.CalledProcessError:
            merged_set = set()

        # ── 2. 获取所有本地分支 + 最后提交信息 ──
        # format: hash|HEAD|date|author|subject
        local_branches = _get_branches_for_each_ref("refs/heads/")

        # ── 3. 可选：获取远程分支 ──
        remote_branches = []
        if remote.lower() == "true":
            remote_branches = _get_branches_for_each_ref("refs/remotes/origin/")

        # ── 4. 组装输出 ──
        def build_entry(b, ref_type="local"):
            name = b["name"]
            is_head = b["head"] == "*"
            merged = name in merged_set
            marker = "→" if is_head else " "
            status = "HEAD+merged" if (is_head and merged) else \
                     "HEAD" if is_head else \
                     "merged" if merged else \
                     "unmerged"
            return (
                f"{marker} {name:<40} [{status:<12}] "
                f"{b['date']}  {b['author']:<20} {b['subject']}"
            )

        lines = []
        lines.append(f"=== 本地分支 ({len(local_branches)} 个) ===")
        if not local_branches:
            lines.append("(无)")
        else:
            lines.append(f"{'':>1} {'分支名':<40} {'状态':<14} {'最后提交':<12}  {'作者':<20} 提交说明")
            lines.append("-" * 120)
            for b in local_branches:
                lines.append(build_entry(b))

        if remote_branches:
            lines.append(f"\n=== 远程分支 ({len(remote_branches)} 个) ===")
            lines.append(f"{'':>1} {'分支名':<40} {'状态':<14} {'最后提交':<12}  {'作者':<20} 提交说明")
            lines.append("-" * 120)
            for b in remote_branches:
                lines.append(build_entry(b, "remote"))

        # ── 5. 统计与摘要 ──
        head_branch = next((b["name"] for b in local_branches if b["head"] == "*"), "?")
        # 分组：HEAD / 已合并 / 未合并，每组列出 分支名(日期)
        head_entries = [f"{b['name']}({b['date']})" for b in local_branches if b["head"] == "*"]
        merged_entries = [
            f"{b['name']}({b['date']})"
            for b in local_branches if b["head"] != "*" and b["name"] in merged_set
        ]
        unmerged_entries = [
            f"{b['name']}({b['date']})"
            for b in local_branches if b["head"] != "*" and b["name"] not in merged_set
        ]

        summary_parts = []
        if head_entries:
            summary_parts.append(f"HEAD: {', '.join(head_entries)}")
        if merged_entries:
            summary_parts.append(f"已合并({len(merged_entries)}个): {', '.join(merged_entries)}")
        if unmerged_entries:
            summary_parts.append(f"未合并({len(unmerged_entries)}个): {', '.join(unmerged_entries)}")
        summary_parts.append(f"共{len(local_branches)}个本地分支")

        detail = "\n".join(lines)

        return {
            "status": "成功",
            "conclusion": f"当前分支 '{head_branch}'，{len(local_branches)} 个本地分支",
            "summary": "，".join(summary_parts),
            "detail": detail,
        }

    except subprocess.CalledProcessError as e:
        return {"status": "失败", "conclusion": f"git branch 执行出错: {e.output.strip()}", "summary": "", "detail": ""}
    except FileNotFoundError:
        return {"status": "失败", "conclusion": "未找到 git 命令，请确认当前目录是 git 仓库。", "summary": "", "detail": ""}
    except Exception as e:
        return {"status": "失败", "conclusion": f"获取分支列表异常: {str(e)}", "summary": "", "detail": ""}


def _get_branches_for_each_ref(ref_pattern: str) -> list[dict]:
    """使用 git for-each-ref 获取分支元数据。"""
    output = subprocess.check_output(
        ["git", "for-each-ref",
         "--format=%(refname:short)|%(HEAD)|%(committerdate:short)|%(authorname)|%(subject)",
         ref_pattern],
        stderr=subprocess.STDOUT, universal_newlines=True
    )
    branches = []
    for line in output.strip().split('\n'):
        if not line.strip():
            continue
        parts = line.split('|', 4)
        if len(parts) < 5:
            continue
        branches.append({
            "name": parts[0],
            "head": parts[1],
            "date": parts[2],
            "author": parts[3],
            "subject": parts[4][:60],  # 截断过长 subject
        })
    # HEAD 分支排最前
    branches.sort(key=lambda b: (0 if b["head"] == "*" else 1, b["name"]))
    return branches
