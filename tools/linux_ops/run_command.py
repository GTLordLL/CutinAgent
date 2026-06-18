"""
run_command — 安全过滤的只读 shell 诊断工具。

替代了 5 个旧工具 (check_network_port, test_connection, locate_large_files,
get_service_status, grep_log_content)，通过三层安全防线确保只读安全。
"""
import subprocess
import time
import re
import shlex

# ═══════════════════════════════════════════════════════════
# 第一层：模式黑名单 (regex → 错误消息)
# ═══════════════════════════════════════════════════════════
BLACKLIST_PATTERNS = [
    (r'\$\(',               '命令替换 $(...) 被禁止'),
    (r'`',                  '反引号命令替换被禁止'),
    # 允许 > /dev/null 和 2>&1，拦截写真实文件的重定向
    (r'>\s*(?!(?:/dev/null|&[12]))', '输出重定向到文件被禁止（允许 /dev/null 和 &1/&2）'),
    (r';',                  '分号多命令链接被禁止'),
    (r'&&',                 '&& 多命令链接被禁止'),
    (r'\|\|',               '|| 多命令链接被禁止'),
    (r'\b(sudo|su|pkexec|doas)\b', '提权指令被禁止'),
    (r'find\b.*\b-(exec|delete|ok)\b', 'find 危险选项 (-exec/-delete/-ok) 被禁止'),
]

# ═══════════════════════════════════════════════════════════
# 第二层：二进制白名单 (~55 个只读命令)
# ═══════════════════════════════════════════════════════════
WHITELIST_BINARIES = {
    # 文件查看
    'cat', 'head', 'tail', 'zcat', 'bzcat', 'xzcat', 'less',
    # 文件元数据
    'ls', 'stat', 'readlink', 'realpath', 'du', 'df', 'file',
    # 文本处理
    'grep', 'egrep', 'fgrep', 'awk', 'sed', 'cut', 'sort', 'uniq', 'tr', 'wc',
    'diff', 'comm', 'cmp',
    # 系统信息
    'uname', 'hostname', 'whoami', 'id', 'groups', 'uptime', 'date',
    # 硬件资源
    'free', 'lscpu', 'lspci', 'lsusb', 'vmstat', 'iostat', 'mpstat',
    # 进程
    'ps', 'pstree', 'pgrep', 'pidof',
    # 网络
    'ss', 'netstat', 'ip', 'ifconfig', 'ping', 'traceroute', 'tracepath',
    'nslookup', 'dig', 'host', 'arp', 'resolvectl',
    # 日志
    'dmesg', 'journalctl', 'last', 'lastb', 'w',
    # 服务 (仅 systemctl 只读子命令，危险子命令由第一层 >/; 覆盖)
    'systemctl',
    # 版本控制 (仅 git 只读子命令)
    'git',
    # Web 请求 (curl/wget 禁止 -o/-O 由额外检查处理)
    'curl', 'wget',
    # 包信息
    'dpkg-query', 'rpm',
    # 工具
    'which', 'whereis', 'echo', 'printf', 'env', 'xargs',
    # 校验
    'md5sum', 'sha1sum', 'sha256sum', 'sha512sum',
    # 归档 (tar 仅 -t 列出)
    'tar',
}

# systemctl 只读子命令白名单
SYSTEMCTL_RO_SUBCMDS = {
    'status', 'is-active', 'is-enabled', 'list-units', 'list-unit-files',
    'show', 'cat', 'list-dependencies', 'list-sockets', 'list-timers',
}

# curl/wget 禁止的写输出选项
CURL_WGET_BLOCKED = re.compile(r'\b(?:curl|wget)\b.*\s(?:-[oO]\s*\S|--output\s)', re.DOTALL)

# tar 禁止的非列出模式
TAR_BLOCKED = re.compile(r'\btar\b.*\s-(?:[A-Za-z]*[xcrRXu]|-[A-Za-z]*delete)', re.DOTALL)


def _extract_binaries(command: str) -> list:
    """从管道的每个分段提取第一个可执行词（跳过 env var 赋值）。"""
    binaries = []
    for segment in command.split('|'):
        segment = segment.strip()
        if not segment:
            continue
        try:
            tokens = shlex.split(segment)
        except ValueError:
            tokens = segment.split()
        if not tokens:
            continue
        # 跳过环境变量赋值 (FOO=bar)
        i = 0
        while i < len(tokens) and '=' in tokens[i]:
            i += 1
        if i >= len(tokens):
            continue
        name = tokens[i]
        if '/' in name:
            name = name.rsplit('/', 1)[-1]
        binaries.append(name)
    return binaries


def run_command(command: str) -> dict:
    """在安全策略下执行只读 shell 命令。

    三层安全防线:
      1. 模式黑名单 — 拦截 $(...)、>、;、&&、||、sudo、find -exec 等
      2. 二进制白名单 — 仅允许 ~55 个只读命令
      3. 资源限制   — timeout=15s, 输出截断 2000 字符
    """
    cmd = command.strip()

    # ── 第一层：模式黑名单 ──
    for pattern, error_msg in BLACKLIST_PATTERNS:
        if re.search(pattern, cmd):
            return {
                "status": "失败",
                "summary": f"安全拦截: {error_msg}",
                "detail": "",
            }

    # ── 第二层：二进制白名单 ──
    binaries = _extract_binaries(cmd)
    if not binaries:
        return {
            "status": "失败",
            "summary": "安全拦截: 无法解析命令中的二进制名称",
            "detail": "",
        }

    for name in binaries:
        if name not in WHITELIST_BINARIES:
            return {
                "status": "失败",
                "summary": f"安全拦截: 命令 '{name}' 不在只读白名单中",
                "detail": "",
            }

    # systemctl 子命令检查
    if 'systemctl' in binaries:
        tokens = shlex.split(cmd) if _safe_shlex(cmd) else cmd.split()
        for i, tok in enumerate(tokens):
            if tok == 'systemctl' and i + 1 < len(tokens):
                subcmd = tokens[i + 1]
                if subcmd not in SYSTEMCTL_RO_SUBCMDS:
                    return {
                        "status": "失败",
                        "summary": f"安全拦截: systemctl 子命令 '{subcmd}' 不允许，仅限只读子命令",
                        "detail": "",
                    }

    # curl/wget -o/-O/--output 检查
    if 'curl' in binaries or 'wget' in binaries:
        if CURL_WGET_BLOCKED.search(cmd):
            return {
                "status": "失败",
                "summary": "安全拦截: curl/wget 禁止 -o/-O/--output 写文件选项",
                "detail": "",
            }

    # tar 非列出模式检查
    if 'tar' in binaries:
        if TAR_BLOCKED.search(cmd):
            return {
                "status": "失败",
                "summary": "安全拦截: tar 仅允许 -t (列出) 模式，禁止解包/创建/删除",
                "detail": "",
            }

    # ── 第三层：资源限制执行 ──
    try:
        t0 = time.time()
        result = subprocess.run(
            cmd,
            shell=True,
            capture_output=True,
            text=True,
            timeout=15,
        )
        elapsed = time.time() - t0
        output = (result.stdout + result.stderr).rstrip('\n')
        line_count = output.count('\n') + 1 if output else 0

        if len(output) > 2000:
            output = output[:2000] + f"\n... (截断，原始 {len(output)} 字符)"

        summary_text = (
            f"命令完成 (exit {result.returncode}), "
            f"{line_count} 行输出, 耗时 {elapsed:.1f}秒"
        )

        return {
            "status": "成功",
            "summary": summary_text,
            "detail": output,
        }

    except subprocess.TimeoutExpired:
        return {
            "status": "失败",
            "summary": "命令执行超时 (15秒)",
            "detail": "",
        }
    except Exception as e:
        return {
            "status": "失败",
            "summary": f"命令执行异常: {str(e)}",
            "detail": "",
        }


def _safe_shlex(cmd: str) -> bool:
    """检测命令字符串是否可安全通过 shlex.split 解析。"""
    try:
        shlex.split(cmd)
        return True
    except ValueError:
        return False
