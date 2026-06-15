"""演示 2：GIT_DAILY_SUMMARY — 每日汇总。

场景：8 个"今日"提交，覆盖 feat/fix/refactor/docs/chore/test 六种类型。
"""

import os
import shutil
from datetime import datetime

from tests.demo_utils import (
    C_CYAN, C_GREEN, C_RESET,
    git_add_commit, git_init, write_file,
)


def setup_demo_daily_summary(repo_dir):
    """搭建演示2仓库：8 个"今日"提交，覆盖 feat/fix/refactor/docs/chore/test。"""
    print(f"  {C_CYAN}[演示2] 搭建 GIT_DAILY_SUMMARY 演示环境 ...{C_RESET}")

    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)

    git_init(repo_dir)

    today = datetime.now().strftime("%Y-%m-%d")

    write_file(repo_dir, "src/__init__.py", "")
    write_file(repo_dir, "src/auth.py", '''\
"""用户认证模块。"""
import hashlib
import hmac
import time
from typing import Optional


def generate_token(user_id: int, secret: str) -> str:
    payload = f"{user_id}:{int(time.time())}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_token(token: str, secret: str) -> Optional[int]:
    try:
        payload, signature = token.rsplit(".", 1)
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        return int(payload.split(":")[0])
    except (ValueError, IndexError):
        return None
''')
    git_add_commit(repo_dir, "feat(auth): add user authentication middleware",
                   date_str=f"{today}T09:00:00")

    write_file(repo_dir, "src/db.py", '''\
"""数据库连接管理。"""
import time
from contextlib import contextmanager


class DatabasePool:
    def __init__(self, dsn: str, pool_size: int = 5):
        self.dsn = dsn
        self.pool_size = pool_size
        self._pool = []

    def acquire(self):
        if not self._pool:
            return self._create_connection()
        return self._pool.pop()

    def release(self, conn):
        if len(self._pool) < self.pool_size:
            self._pool.append(conn)

    def _create_connection(self):
        time.sleep(0.01)
        return {"dsn": self.dsn, "id": id(self)}
''')
    git_add_commit(repo_dir, "fix(db): resolve connection timeout after idle period",
                   date_str=f"{today}T10:30:00")

    write_file(repo_dir, "src/validators.py", '''\
"""数据校验模块。"""
import re
from typing import Optional


def validate_email(email: str) -> bool:
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_username(username: str) -> Optional[str]:
    if len(username) < 3:
        return "用户名至少需要 3 个字符"
    if len(username) > 32:
        return "用户名不能超过 32 个字符"
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", username):
        return "用户名必须以字母开头，只能包含字母、数字和下划线"
    return None


def validate_password_strength(password: str) -> tuple[bool, str]:
    if len(password) < 8:
        return False, "密码至少 8 位"
    if not re.search(r"[A-Z]", password):
        return False, "需要包含大写字母"
    if not re.search(r"[a-z]", password):
        return False, "需要包含小写字母"
    if not re.search(r"\d", password):
        return False, "需要包含数字"
    return True, "密码强度合格"
''')
    write_file(repo_dir, "src/auth.py", '''\
"""用户认证模块。"""
import hashlib
import hmac
import time
from typing import Optional
from src.validators import validate_username


def generate_token(user_id: int, secret: str) -> str:
    payload = f"{user_id}:{int(time.time())}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_token(token: str, secret: str) -> Optional[int]:
    try:
        payload, signature = token.rsplit(".", 1)
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        return int(payload.split(":")[0])
    except (ValueError, IndexError):
        return None


def register_user(username: str, password: str) -> dict:
    error = validate_username(username)
    if error:
        return {"success": False, "error": error}
    return {"success": True, "username": username}
''')
    git_add_commit(repo_dir, "refactor(validators): extract validation logic to separate module",
                   date_str=f"{today}T11:45:00")

    write_file(repo_dir, "README.md", '''\
# MiniAuth — 轻量认证服务

## API 文档

### POST /auth/login
用户登录，返回认证令牌。

### POST /auth/register
注册新用户，含用户名/密码/邮箱校验。

### GET /auth/verify
验证令牌有效性。

## 模块结构
- `src/auth.py` — 认证令牌生成与验证
- `src/db.py` — 数据库连接池
- `src/validators.py` — 输入校验工具
''')
    git_add_commit(repo_dir, "docs(api): update endpoint documentation with examples",
                   date_str=f"{today}T13:00:00")

    write_file(repo_dir, "src/auth.py", '''\
"""用户认证模块（含速率限制）。"""
import hashlib
import hmac
import time
from collections import defaultdict
from typing import Optional
from src.validators import validate_username


_login_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_LOGIN_ATTEMPTS = 5
_RATE_WINDOW = 300


def generate_token(user_id: int, secret: str) -> str:
    payload = f"{user_id}:{int(time.time())}"
    signature = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def verify_token(token: str, secret: str) -> Optional[int]:
    try:
        payload, signature = token.rsplit(".", 1)
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        return int(payload.split(":")[0])
    except (ValueError, IndexError):
        return None


def register_user(username: str, password: str) -> dict:
    error = validate_username(username)
    if error:
        return {"success": False, "error": error}
    return {"success": True, "username": username}


def check_rate_limit(identifier: str) -> bool:
    now = time.monotonic()
    attempts = _login_attempts[identifier]
    _login_attempts[identifier] = [t for t in attempts if now - t < _RATE_WINDOW]
    if len(_login_attempts[identifier]) >= _MAX_LOGIN_ATTEMPTS:
        return False
    _login_attempts[identifier].append(now)
    return True
''')
    git_add_commit(repo_dir, "feat(security): add rate limiting for login endpoint",
                   date_str=f"{today}T14:30:00")

    write_file(repo_dir, "src/api/handler.py", '''\
"""API 请求处理。"""
from typing import Optional


def paginate(items: list, page: int = 1, page_size: int = 20) -> dict:
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    offset = (page - 1) * page_size
    if offset < 0:
        offset = 0
    return {
        "data": items[offset:offset + page_size],
        "page": page, "page_size": page_size,
        "total": total, "total_pages": total_pages,
    }
''')
    git_add_commit(repo_dir, "fix(api): correct pagination offset calculation",
                   date_str=f"{today}T16:00:00")

    write_file(repo_dir, "requirements.txt", '''\
cryptography==42.0.5
pydantic==2.7.1
sqlalchemy==2.0.30
pytest==8.2.0
black==24.4.0
''')
    git_add_commit(repo_dir, "chore(deps): update dependencies and pin versions",
                   date_str=f"{today}T17:15:00")

    write_file(repo_dir, "tests/__init__.py", "")
    write_file(repo_dir, "tests/test_auth.py", '''\
"""认证模块集成测试。"""
import pytest
from src.auth import generate_token, verify_token, check_rate_limit


class TestTokenGeneration:
    SECRET = "test-secret-key"

    def test_generate_and_verify_valid_token(self):
        token = generate_token(user_id=42, secret=self.SECRET)
        assert "." in token
        user_id = verify_token(token, secret=self.SECRET)
        assert user_id == 42

    def test_verify_tampered_token(self):
        token = generate_token(user_id=1, secret=self.SECRET)
        parts = token.split(".")
        tampered = f"999:999999.{parts[1]}"
        assert verify_token(tampered, secret=self.SECRET) is None

    def test_verify_with_wrong_secret(self):
        token = generate_token(user_id=7, secret=self.SECRET)
        assert verify_token(token, secret="wrong-secret") is None


class TestRateLimiter:
    def test_rejects_after_limit(self):
        user = "ratelimit-test-user"
        for _ in range(5):
            check_rate_limit(user)
        assert check_rate_limit(user) is False
''')
    git_add_commit(repo_dir, "test(auth): add integration tests for authentication flow",
                   date_str=f"{today}T18:30:00")

    print(f"         {C_GREEN}提交就绪{C_RESET}: 8 条今日提交 (feat×2 / fix×2 / refactor / docs / chore / test)")
