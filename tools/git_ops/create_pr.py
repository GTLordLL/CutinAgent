import re
import subprocess


def _parse_title(data: str) -> str:
    """从 PR 描述中解析标题。匹配 '## PR 标题\n[类型] xxx' 格式。"""
    # 匹配 "## PR 标题" 之后的下一行非空内容
    m = re.search(r'##\s*PR\s*标题\s*\n+\s*(\[?.+]?.+)', data)
    if m:
        title = m.group(1).strip()
        # 去掉可能的 markdown 标记残留
        title = re.sub(r'^#+\s*', '', title)
        return title[:256]  # GitHub title 限制 256 字符
    # fallback: 取第一个非空非标题行
    for line in data.split('\n'):
        stripped = line.strip()
        if stripped and not stripped.startswith('#'):
            return stripped[:256]
    return "Pull Request"


def create_pr(data: str, base: str = "main", draft: str = "false") -> dict:
    """调用 gh CLI 从 PR 描述文本创建 GitHub Pull Request。

    Args:
        data: PR 描述全文（必填），通常引用 VAR_generate_pr_description。
        base: 目标分支，默认 main。
        draft: 是否创建 draft PR，"true"/"false"，默认 false。
    """
    try:
        # ── 1. 检查 gh CLI 是否可用 ──
        try:
            subprocess.check_output(
                ["gh", "--version"],
                stderr=subprocess.STDOUT, universal_newlines=True
            )
        except FileNotFoundError:
            return {
                "status": "失败",
                "summary": "未找到 gh CLI，请安装 GitHub CLI 并执行 gh auth login 进行认证。",
                "detail": "",
            }

        # ── 2. 检查认证状态 ──
        try:
            subprocess.check_output(
                ["gh", "auth", "status"],
                stderr=subprocess.STDOUT, universal_newlines=True
            )
        except subprocess.CalledProcessError:
            return {
                "status": "失败",
                "summary": "gh 未登录，请执行 gh auth login 进行认证。",
                "detail": "",
            }

        # ── 3. 获取当前分支作为 head ──
        try:
            head = subprocess.check_output(
                ["git", "branch", "--show-current"],
                stderr=subprocess.STDOUT, universal_newlines=True
            ).strip()
        except subprocess.CalledProcessError:
            return {
                "status": "失败",
                "summary": "无法获取当前分支名，请确认在 git 仓库中。",
                "detail": "",
            }

        if not head:
            return {
                "status": "失败",
                "summary": "当前处于 detached HEAD 状态，无法创建 PR。",
                "detail": "",
            }

        # ── 4. 解析标题 ──
        title = _parse_title(data)

        # ── 5. 检查是否已存在 PR ──
        try:
            existing = subprocess.check_output(
                ["gh", "pr", "list", "--head", head, "--state", "open",
                 "--json", "url", "--jq", ".[0].url"],
                stderr=subprocess.STDOUT, universal_newlines=True
            ).strip()
        except subprocess.CalledProcessError:
            existing = ""

        if existing:
            return {
                "status": "失败",
                "summary": f"分支 '{head}' 已存在 PR: {existing}",
                "detail": existing,
            }

        # ── 6. 构建 gh pr create 命令 ──
        cmd = [
            "gh", "pr", "create",
            "--base", base,
            "--head", head,
            "--title", title,
            "--body", data,
        ]

        if draft.lower() == "true":
            cmd.append("--draft")

        # ── 7. 执行创建 ──
        output = subprocess.check_output(
            cmd, stderr=subprocess.STDOUT, universal_newlines=True
        ).strip()

        return {
            "status": "成功",
            "summary": f"PR: {title} => {output}",
            "detail": output,
        }

    except subprocess.CalledProcessError as e:
        err = e.output.strip() if e.output else str(e)
        return {
            "status": "失败",
            "summary": f"gh pr create 执行出错: {err}",
            "detail": err,
        }
    except FileNotFoundError:
        return {
            "status": "失败",
            "summary": "未找到 gh CLI，请安装 GitHub CLI 并执行 gh auth login 进行认证。",
            "detail": "",
        }
    except Exception as e:
        return {
            "status": "失败",
            "summary": f"创建 PR 过程异常: {str(e)}",
            "detail": "",
        }
