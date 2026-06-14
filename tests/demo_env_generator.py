#!/usr/bin/env python3
"""Git SOP 演示环境生成器。

在 tmp/ 下生成两个逼真的 Git 演示仓库，用于录制 GIT_SMART_COMMIT 和
GIT_DAILY_SUMMARY 两个 SOP 的视频演示。可随时生成和删除。

用法:
    python tests/demo_env_generator.py --setup          # 生成全部演示环境
    python tests/demo_env_generator.py --setup --demo 1  # 仅生成演示1
    python tests/demo_env_generator.py --setup --demo 2  # 仅生成演示2
    python tests/demo_env_generator.py --show            # 展示环境状态 + 演示脚本
    python tests/demo_env_generator.py --clean           # 删除所有演示环境
"""

import argparse
import os
import shutil
import subprocess
import sys
from datetime import datetime

# ---------- 路径常量 ----------
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
TMP_DIR = os.path.join(PROJECT_ROOT, "tmp")
DEMO1_DIR = os.path.join(TMP_DIR, "demo_smart_commit")
DEMO2_DIR = os.path.join(TMP_DIR, "demo_daily_summary")

# ---------- ANSI 颜色 ----------
C_BOLD = "\033[1m"
C_GREEN = "\033[32m"
C_YELLOW = "\033[33m"
C_CYAN = "\033[36m"
C_MAGENTA = "\033[35m"
C_RESET = "\033[0m"


def run(cmd, cwd=None, env=None, check=True):
    """执行 shell 命令，返回 CompletedProcess。"""
    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)
    return subprocess.run(
        cmd, cwd=cwd, env=merged_env,
        capture_output=True, text=True, check=check,
    )


def git_init(repo_dir):
    """初始化 git 仓库并配置用户信息。"""
    os.makedirs(repo_dir, exist_ok=True)
    run(["git", "init"], cwd=repo_dir)
    run(["git", "config", "user.name", "张三"], cwd=repo_dir)
    run(["git", "config", "user.email", "zhangsan@example.com"], cwd=repo_dir)


def write_file(repo_dir, path, content):
    """在仓库中写入文件，自动创建父目录。"""
    full = os.path.join(repo_dir, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w", encoding="utf-8") as f:
        f.write(content)


def git_add_commit(repo_dir, message, date_str=None):
    """git add -A + git commit，可选指定提交日期。"""
    env = {}
    if date_str:
        env["GIT_COMMITTER_DATE"] = date_str
        env["GIT_AUTHOR_DATE"] = date_str
    run(["git", "add", "-A"], cwd=repo_dir)
    run(["git", "commit", "-m", message], cwd=repo_dir, env=env if env else None)


# ============================================================
# 演示 1：GIT_SMART_COMMIT
# ============================================================

def setup_demo_smart_commit(repo_dir):
    """搭建演示1仓库：初始项目 + 混合变更（修改/新增/删除）。"""
    print(f"  {C_CYAN}[演示1] 搭建 GIT_SMART_COMMIT 演示环境 ...{C_RESET}")

    # -- 清理旧仓库 --
    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)

    git_init(repo_dir)

    # -- 初始提交：一个"半成品"Python 项目 --
    write_file(repo_dir, "src/__init__.py", "")

    write_file(repo_dir, "src/api/handler.py", '''\
"""HTTP 请求处理模块。"""

import time
import logging

logger = logging.getLogger(__name__)


def fetch_user_profile(user_id: int) -> dict:
    """从远程 API 获取用户资料。"""
    logger.info(f"正在获取用户 {user_id} 的资料 ...")
    try:
        # 模拟 HTTP 请求
        time.sleep(0.5)
        response = _make_request(f"/users/{user_id}")
        return response.json()
    except Exception:
        logger.error(f"获取用户 {user_id} 资料失败")
        return {}


def fetch_order_list(user_id: int, page: int = 1) -> list:
    """获取用户订单列表。"""
    logger.info(f"正在获取用户 {user_id} 的订单，第 {page} 页")
    try:
        response = _make_request(f"/users/{user_id}/orders?page={page}")
        return response.json().get("data", [])
    except Exception:
        logger.error(f"获取订单列表失败")
        return []


def _make_request(endpoint: str):
    """底层 HTTP 请求（模拟）。"""
    # TODO: 实现真实的 HTTP 客户端
    import random
    if random.random() < 0.05:
        raise ConnectionError("模拟网络错误")
    return type("Response", (), {"json": lambda: {"data": []}})()
''')

    write_file(repo_dir, "src/models/user.py", '''\
"""用户数据模型。"""

from dataclasses import dataclass
from typing import Optional


@dataclass
class User:
    """用户实体。"""
    id: int
    username: str
    email: str
    display_name: str
    avatar_url: Optional[str] = None
    is_active: bool = True

    @property
    def profile_url(self) -> str:
        return f"/users/{self.id}"


@dataclass
class Order:
    """订单实体。"""
    id: int
    user_id: int
    product_name: str
    quantity: int
    total_price: float
    status: str = "pending"
''')

    write_file(repo_dir, "README.md", '''\
# MyShop API Client

一个简单的电商 API 客户端库，用于管理用户和订单。

## 功能

- 获取用户资料
- 查询订单列表
- 用户和订单数据模型

## 安装

```bash
pip install -r requirements.txt
```

## 使用

```python
from src.api.handler import fetch_user_profile

user = fetch_user_profile(1)
print(user)
```
''')

    write_file(repo_dir, "requirements.txt", '''\
requests==2.28.0
dataclasses==0.8
''')

    git_add_commit(repo_dir, "init: 初始化项目骨架（API客户端 + 数据模型）")

    print(f"         初始提交完成: 4 个文件")

    # -- 制造混合变更：修改 + 新增 + 删除 --

    # 1) 修改 src/api/handler.py：精细化异常处理 + 增加重试机制
    write_file(repo_dir, "src/api/handler.py", '''\
"""HTTP 请求处理模块（含超时重试与精细化异常处理）。"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# 自定义异常类
class RequestTimeout(Exception):
    """请求超时。"""
    pass


class APIError(Exception):
    """服务端返回错误。"""
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"API 错误 [{status_code}]: {message}")


def fetch_user_profile(user_id: int) -> Optional[dict]:
    """从远程 API 获取用户资料，含自动重试。"""
    logger.info(f"正在获取用户 {user_id} 的资料 ...")
    max_retries = 3
    for attempt in range(max_retries):
        try:
            response = _make_request(f"/users/{user_id}")
            return response.json()
        except RequestTimeout as e:
            logger.warning(f"请求超时，第 {attempt + 1}/{max_retries} 次重试")
            if attempt == max_retries - 1:
                logger.error(f"获取用户 {user_id} 资料失败: 超过最大重试次数")
                return None
            time.sleep(1 * (attempt + 1))  # 递增退避
        except ConnectionError as e:
            logger.error(f"连接错误: {e}")
            return None
        except APIError as e:
            logger.error(f"API 返回错误 [{e.status_code}]: {e.message}")
            return None
    return None


def fetch_order_list(user_id: int, page: int = 1, page_size: int = 20) -> list:
    """获取用户订单列表，支持分页。"""
    logger.info(f"正在获取用户 {user_id} 的订单，第 {page} 页")
    try:
        response = _make_request(
            f"/users/{user_id}/orders?page={page}&page_size={page_size}"
        )
        return response.json().get("data", [])
    except RequestTimeout as e:
        logger.error(f"获取订单列表超时: {e}")
        return []
    except ConnectionError as e:
        logger.error(f"获取订单列表连接失败: {e}")
        return []
    except APIError as e:
        logger.error(f"获取订单列表失败 [{e.status_code}]: {e.message}")
        return []


def _make_request(endpoint: str, timeout: int = 10):
    """底层 HTTP 请求（模拟实现）。"""
    import random
    if random.random() < 0.02:
        raise ConnectionError("模拟网络连接错误")
    if random.random() < 0.05:
        raise RequestTimeout(f"请求 {endpoint} 超时（>{timeout}s）")
    # 正常响应
    return type("Response", (), {
        "json": lambda: {"data": []},
        "status_code": 200,
    })()
''')

    # 2) 新增 src/utils/cache.py
    write_file(repo_dir, "src/utils/__init__.py", "")
    write_file(repo_dir, "src/utils/cache.py", '''\
"""简单的 LRU 缓存装饰器，支持 TTL 过期。"""

import functools
import time
from collections import OrderedDict
from threading import Lock


class LRUCache:
    """线程安全的 LRU 缓存，支持 TTL 过期。"""

    def __init__(self, maxsize: int = 128, ttl: float = 300):
        self.maxsize = maxsize
        self.ttl = ttl
        self._cache: OrderedDict = OrderedDict()
        self._lock = Lock()

    def get(self, key):
        with self._lock:
            if key not in self._cache:
                return None
            value, timestamp = self._cache[key]
            if time.monotonic() - timestamp > self.ttl:
                del self._cache[key]
                return None
            self._cache.move_to_end(key)
            return value

    def set(self, key, value):
        with self._lock:
            if key in self._cache:
                self._cache.move_to_end(key)
            self._cache[key] = (value, time.monotonic())
            while len(self._cache) > self.maxsize:
                self._cache.popitem(last=False)

    def clear(self):
        with self._lock:
            self._cache.clear()


def lru_cache(maxsize: int = 128, ttl: float = 300):
    """装饰器：为函数调用添加 LRU + TTL 缓存。"""
    cache = LRUCache(maxsize=maxsize, ttl=ttl)

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            key = (args, tuple(sorted(kwargs.items())))
            result = cache.get(key)
            if result is not None:
                return result
            result = func(*args, **kwargs)
            cache.set(key, result)
            return result

        wrapper.cache = cache
        return wrapper

    return decorator
''')

    # 3) 删除 src/models/user.py
    os.remove(os.path.join(repo_dir, "src/models/user.py"))
    # 如果 models 目录变空，删除目录
    models_dir = os.path.join(repo_dir, "src/models")
    if os.path.isdir(models_dir) and not os.listdir(models_dir):
        os.rmdir(models_dir)

    # 4) 修改 README.md
    write_file(repo_dir, "README.md", '''\
# MyShop API Client v0.2

一个健壮的电商 API 客户端库，支持用户管理、订单查询和数据缓存。

## 功能

- 获取用户资料（含超时重试与精细化异常处理）
- 查询订单列表（支持分页）
- LRU 内存缓存，减少重复 API 调用
- 自定义异常类：`RequestTimeout`, `APIError`

## 安装

```bash
pip install -r requirements.txt
```

## 快速开始

```python
from src.api.handler import fetch_user_profile
from src.utils.cache import lru_cache

# 带缓存的调用
@lru_cache(maxsize=64, ttl=120)
def get_user_cached(user_id):
    return fetch_user_profile(user_id)

user = get_user_cached(1)
print(user)
```

## 依赖

- Python 3.10+
- requests >= 2.28
''')

    print(f"         {C_GREEN}变更就绪{C_RESET}: 修改 2 个文件, 新增 1 个文件, 删除 1 个文件")


# ============================================================
# 演示 2：GIT_DAILY_SUMMARY
# ============================================================

def setup_demo_daily_summary(repo_dir):
    """搭建演示2仓库：8 个"今日"提交，覆盖 feat/fix/refactor/docs/chore/test。"""
    print(f"  {C_CYAN}[演示2] 搭建 GIT_DAILY_SUMMARY 演示环境 ...{C_RESET}")

    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)

    git_init(repo_dir)

    today = datetime.now().strftime("%Y-%m-%d")

    # -- 提交 1: feat(auth) 9:00 --
    write_file(repo_dir, "src/__init__.py", "")
    write_file(repo_dir, "src/auth.py", '''\
"""用户认证模块。"""

import hashlib
import hmac
import time
from typing import Optional


def generate_token(user_id: int, secret: str) -> str:
    """为用户生成 JWT 风格的认证令牌。"""
    payload = f"{user_id}:{int(time.time())}"
    signature = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_token(token: str, secret: str) -> Optional[int]:
    """验证令牌，返回 user_id 或 None。"""
    try:
        payload, signature = token.rsplit(".", 1)
        expected = hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        user_id_str = payload.split(":")[0]
        return int(user_id_str)
    except (ValueError, IndexError):
        return None
''')
    git_add_commit(repo_dir, "feat(auth): add user authentication middleware",
                   date_str=f"{today}T09:00:00")

    # -- 提交 2: fix(db) 10:30 --
    write_file(repo_dir, "src/db.py", '''\
"""数据库连接管理。"""

import time
from contextlib import contextmanager


class DatabasePool:
    """简易数据库连接池。"""

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
        # 模拟数据库连接
        time.sleep(0.01)
        return {"dsn": self.dsn, "id": id(self)}
''')
    git_add_commit(repo_dir, "fix(db): resolve connection timeout after idle period",
                   date_str=f"{today}T10:30:00")

    # -- 提交 3: refactor(validators) 11:45 --
    write_file(repo_dir, "src/validators.py", r'''\
"""数据校验模块。"""

import re
from typing import Optional


def validate_email(email: str) -> bool:
    """校验邮箱格式。"""
    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"
    return bool(re.match(pattern, email))


def validate_username(username: str) -> Optional[str]:
    """校验用户名，返回错误信息或 None。"""
    if len(username) < 3:
        return "用户名至少需要 3 个字符"
    if len(username) > 32:
        return "用户名不能超过 32 个字符"
    if not re.match(r"^[a-zA-Z][a-zA-Z0-9_]*$", username):
        return "用户名必须以字母开头，只能包含字母、数字和下划线"
    return None


def validate_password_strength(password: str) -> tuple[bool, str]:
    """校验密码强度，返回 (是否通过, 原因)。"""
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
    # 修改 auth.py 引用 validators
    write_file(repo_dir, "src/auth.py", '''\
"""用户认证模块。"""

import hashlib
import hmac
import time
from typing import Optional

from src.validators import validate_username


def generate_token(user_id: int, secret: str) -> str:
    """为用户生成 JWT 风格的认证令牌。"""
    payload = f"{user_id}:{int(time.time())}"
    signature = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_token(token: str, secret: str) -> Optional[int]:
    """验证令牌，返回 user_id 或 None。"""
    try:
        payload, signature = token.rsplit(".", 1)
        expected = hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        user_id_str = payload.split(":")[0]
        return int(user_id_str)
    except (ValueError, IndexError):
        return None


def register_user(username: str, password: str) -> dict:
    """注册新用户（含用户名校验）。"""
    error = validate_username(username)
    if error:
        return {"success": False, "error": error}
    return {"success": True, "username": username}
''')
    git_add_commit(repo_dir,
                   "refactor(validators): extract validation logic to separate module",
                   date_str=f"{today}T11:45:00")

    # -- 提交 4: docs(api) 13:00 --
    write_file(repo_dir, "README.md", '''\
# MiniAuth — 轻量认证服务

一个 Python 实现的轻量级用户认证与授权微服务。

## API 文档

### POST /auth/login
用户登录，返回认证令牌。

**请求体：**
```json
{"username": "alice", "password": "s3cr3tP@ss"}
```

**响应：**
```json
{"token": "1:1717000000.abc123...", "expires_in": 3600}
```

### POST /auth/register
注册新用户。

**请求体：**
```json
{"username": "alice", "password": "s3cr3tP@ss", "email": "alice@example.com"}
```

**校验规则：**
- 用户名 3-32 字符，字母开头
- 密码至少 8 位，含大小写字母和数字
- 邮箱格式校验

### GET /auth/verify
验证令牌有效性。

**请求头：**
```
Authorization: Bearer <token>
```

**响应：**
```json
{"valid": true, "user_id": 1}
```

## 模块结构

- `src/auth.py` — 认证令牌生成与验证
- `src/db.py` — 数据库连接池
- `src/validators.py` — 输入校验工具
''')
    git_add_commit(repo_dir, "docs(api): update endpoint documentation with examples",
                   date_str=f"{today}T13:00:00")

    # -- 提交 5: feat(security) 14:30 --
    write_file(repo_dir, "src/auth.py", '''\
"""用户认证模块（含速率限制）。"""

import hashlib
import hmac
import time
from collections import defaultdict
from typing import Optional

from src.validators import validate_username


# 简易内存速率限制器
_login_attempts: dict[str, list[float]] = defaultdict(list)
_MAX_LOGIN_ATTEMPTS = 5
_RATE_WINDOW = 300  # 5 分钟窗口


def generate_token(user_id: int, secret: str) -> str:
    """为用户生成 JWT 风格的认证令牌。"""
    payload = f"{user_id}:{int(time.time())}"
    signature = hmac.new(
        secret.encode(), payload.encode(), hashlib.sha256
    ).hexdigest()
    return f"{payload}.{signature}"


def verify_token(token: str, secret: str) -> Optional[int]:
    """验证令牌，返回 user_id 或 None。"""
    try:
        payload, signature = token.rsplit(".", 1)
        expected = hmac.new(
            secret.encode(), payload.encode(), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(signature, expected):
            return None
        user_id_str = payload.split(":")[0]
        return int(user_id_str)
    except (ValueError, IndexError):
        return None


def register_user(username: str, password: str) -> dict:
    """注册新用户（含用户名校验）。"""
    error = validate_username(username)
    if error:
        return {"success": False, "error": error}
    return {"success": True, "username": username}


def check_rate_limit(identifier: str) -> bool:
    """检查是否超过速率限制，返回 True 表示允许继续。"""
    now = time.monotonic()
    attempts = _login_attempts[identifier]
    # 清理过期记录
    _login_attempts[identifier] = [
        t for t in attempts if now - t < _RATE_WINDOW
    ]
    if len(_login_attempts[identifier]) >= _MAX_LOGIN_ATTEMPTS:
        return False
    _login_attempts[identifier].append(now)
    return True
''')
    git_add_commit(repo_dir,
                   "feat(security): add rate limiting for login endpoint",
                   date_str=f"{today}T14:30:00")

    # -- 提交 6: fix(api) 16:00 --
    write_file(repo_dir, "src/api/handler.py", '''\
"""API 请求处理。"""

from typing import Optional


def paginate(items: list, page: int = 1, page_size: int = 20) -> dict:
    """对列表进行分页，返回分页结果。"""
    total = len(items)
    total_pages = max(1, (total + page_size - 1) // page_size)
    # 修正：page 从 0 开始计算偏移
    offset = (page - 1) * page_size
    if offset < 0:
        offset = 0
    return {
        "data": items[offset:offset + page_size],
        "page": page,
        "page_size": page_size,
        "total": total,
        "total_pages": total_pages,
    }


def handle_request(endpoint: str, method: str = "GET",
                   body: Optional[dict] = None) -> dict:
    """统一请求处理入口。"""
    # 模拟路由分发
    routes = {
        "GET /health": lambda: {"status": "ok"},
        "POST /auth/login": lambda: {"token": "xxx.yyy"},
    }
    key = f"{method} {endpoint}"
    handler = routes.get(key)
    if handler is None:
        return {"error": "not_found", "status_code": 404}
    return handler()
''')
    git_add_commit(repo_dir,
                   "fix(api): correct pagination offset calculation for page boundaries",
                   date_str=f"{today}T16:00:00")

    # -- 提交 7: chore(deps) 17:15 --
    write_file(repo_dir, "requirements.txt", '''\
# Core
cryptography==42.0.5
pydantic==2.7.1

# Database
sqlalchemy==2.0.30
aiosqlite==0.20.0

# Dev
pytest==8.2.0
pytest-cov==5.0.0
black==24.4.0
ruff==0.4.4
''')
    git_add_commit(repo_dir, "chore(deps): update dependencies and pin versions",
                   date_str=f"{today}T17:15:00")

    # -- 提交 8: test(auth) 18:30 --
    write_file(repo_dir, "tests/__init__.py", "")
    write_file(repo_dir, "tests/test_auth.py", '''\
"""认证模块集成测试。"""

import pytest
from src.auth import generate_token, verify_token, check_rate_limit


class TestTokenGeneration:
    """令牌生成与验证测试。"""

    SECRET = "test-secret-key"

    def test_generate_and_verify_valid_token(self):
        token = generate_token(user_id=42, secret=self.SECRET)
        assert "." in token
        user_id = verify_token(token, secret=self.SECRET)
        assert user_id == 42

    def test_verify_tampered_token(self):
        token = generate_token(user_id=1, secret=self.SECRET)
        # 篡改 payload 部分
        parts = token.split(".")
        tampered = f"999:999999.{parts[1]}"
        assert verify_token(tampered, secret=self.SECRET) is None

    def test_verify_with_wrong_secret(self):
        token = generate_token(user_id=7, secret=self.SECRET)
        assert verify_token(token, secret="wrong-secret") is None

    def test_verify_malformed_token(self):
        assert verify_token("not.a.token", secret=self.SECRET) is None
        assert verify_token("", secret=self.SECRET) is None


class TestRateLimiter:
    """速率限制测试。"""

    def test_allows_requests_within_limit(self):
        # 注意：check_rate_limit 使用内存存储，测试顺序敏感
        for i in range(5):
            assert check_rate_limit(f"test-user-{i}") is True

    def test_rejects_after_limit(self):
        user = "ratelimit-test-user"
        for _ in range(5):
            check_rate_limit(user)
        assert check_rate_limit(user) is False
''')
    git_add_commit(repo_dir,
                   "test(auth): add integration tests for authentication flow",
                   date_str=f"{today}T18:30:00")

    print(f"         {C_GREEN}提交就绪{C_RESET}: 8 条今日提交 (feat×2 / fix×2 / refactor / docs / chore / test)")


# ============================================================
# show / clean
# ============================================================

def show_demo_status():
    """展示演示环境状态和录制脚本。"""
    print(f"\n{C_BOLD}{'='*60}{C_RESET}")
    print(f"{C_BOLD}  Git SOP 演示环境状态{C_RESET}")
    print(f"{C_BOLD}{'='*60}{C_RESET}\n")

    # -- 演示 1 --
    has_demo1 = os.path.isdir(os.path.join(DEMO1_DIR, ".git"))
    status1 = f"{C_GREEN}✓ 就绪{C_RESET}" if has_demo1 else f"{C_YELLOW}✗ 未生成{C_RESET}"
    print(f"  {C_BOLD}演示 1: GIT_SMART_COMMIT{C_RESET}  [{status1}]")
    print(f"  路径: {DEMO1_DIR}")
    if has_demo1:
        # git status
        r = run(["git", "status", "--porcelain"], cwd=DEMO1_DIR, check=False)
        lines = r.stdout.strip().split("\n") if r.stdout.strip() else []
        mods = sum(1 for l in lines if l and l[1] == "M" or (len(l) > 2 and l[:2] == " M"))
        adds = sum(1 for l in lines if l and l.startswith("??"))
        dels = sum(1 for l in lines if l and (" D" in l[:3] or l.startswith("D ")))
        print(f"  变更: {C_YELLOW}修改×{mods}{C_RESET}  {C_GREEN}新增×{adds}{C_RESET}  {C_MAGENTA}删除×{dels}{C_RESET}")

    print()

    # -- 演示 2 --
    has_demo2 = os.path.isdir(os.path.join(DEMO2_DIR, ".git"))
    status2 = f"{C_GREEN}✓ 就绪{C_RESET}" if has_demo2 else f"{C_YELLOW}✗ 未生成{C_RESET}"
    print(f"  {C_BOLD}演示 2: GIT_DAILY_SUMMARY{C_RESET}  [{status2}]")
    print(f"  路径: {DEMO2_DIR}")
    if has_demo2:
        r = run(["git", "log", "--since=midnight", "--oneline"], cwd=DEMO2_DIR, check=False)
        count = len(r.stdout.strip().split("\n")) if r.stdout.strip() else 0
        print(f"  今日提交: {C_GREEN}{count} 条{C_RESET}")

    # -- 演示脚本 --
    if has_demo1 or has_demo2:
        print(f"\n{C_BOLD}{'='*60}{C_RESET}")
        print(f"{C_BOLD}  📋 录制演示脚本{C_RESET}")
        print(f"{C_BOLD}{'='*60}{C_RESET}")

        if has_demo1:
            print(f"""
{C_CYAN}{'─'*60}{C_RESET}
{C_BOLD} 演示 1 — GIT_SMART_COMMIT（智能提交）{C_RESET}
{C_CYAN}{'─'*60}{C_RESET}

# 步骤 1：展示混乱的工作区
{C_YELLOW}cd {DEMO1_DIR}{C_RESET}
{C_YELLOW}git status{C_RESET}
{C_YELLOW}git diff --stat{C_RESET}

# 步骤 2：启动 Agent
{C_YELLOW}cutin{C_RESET}

# 步骤 3：输入指令（在 REPL 中输入）
> {C_GREEN}帮我分析当前改动，生成一个规范的 commit message 并提交{C_RESET}

# → Agent 流式输出 Thinker 推理过程（录制亮点）
# → 输出分析结果 + commit message 建议
# → 确认执行 → git add + git commit

# 步骤 4：验证提交结果
{C_YELLOW}git log -1 --format="%h %s%n%b"{C_RESET}

{C_BOLD}🎬 录制要点：{C_RESET}
  1. git status 展示三种变更（M/A/D）→ 给观众"很乱"的视觉印象
  2. Thinker 流式推理是核心亮点，保持镜头对准终端
  3. commit message 生成后给 3 秒停留，让观众看清楚内容
  4. git log -1 验证时放大终端字体
""")

        if has_demo2:
            print(f"""
{C_CYAN}{'─'*60}{C_RESET}
{C_BOLD} 演示 2 — GIT_DAILY_SUMMARY（每日汇总）{C_RESET}
{C_CYAN}{'─'*60}{C_RESET}

# 步骤 1：展示今日提交量
{C_YELLOW}cd {DEMO2_DIR}{C_RESET}
{C_YELLOW}git log --since=midnight --oneline{C_RESET}

# 步骤 2：启动 Agent
{C_YELLOW}cutin{C_RESET}

# 步骤 3：输入指令
> {C_GREEN}生成今天的开发工作总结{C_RESET}

# → Agent 读取 git log → 按 feat/fix/refactor/docs 归类
# → 生成结构化日报

{C_BOLD}🎬 录制要点：{C_RESET}
  1. 先展示 git log 的 8 条提交 → 让观众看到"很多提交需要归纳"
  2. Agent 归类过程是亮点（跨多条 commit 做语义归纳）
  3. 最终日报停留 5 秒，让观众阅读分类结果
""")

    # -- 提示 --
    if not has_demo1 and not has_demo2:
        print(f"\n  {C_YELLOW}环境未生成，请先运行:{C_RESET}")
        print(f"  python tests/demo_env_generator.py --setup\n")
    else:
        print(f"{C_BOLD}{'='*60}{C_RESET}")
        print(f"  清理环境: {C_YELLOW}python tests/demo_env_generator.py --clean{C_RESET}")
        print(f"{C_BOLD}{'='*60}{C_RESET}\n")


def clean_demo_envs():
    """删除所有演示环境。"""
    print(f"  {C_YELLOW}清理演示环境 ...{C_RESET}")
    for d in [DEMO1_DIR, DEMO2_DIR]:
        if os.path.isdir(d):
            shutil.rmtree(d)
            print(f"    已删除: {d}")
    # 如果 tmp 目录为空，也删除
    if os.path.isdir(TMP_DIR) and not os.listdir(TMP_DIR):
        os.rmdir(TMP_DIR)
        print(f"    已删除空目录: {TMP_DIR}")
    print(f"  {C_GREEN}清理完成{C_RESET}")


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(
        description="Git SOP 演示环境生成器 — 在 tmp/ 下生成可随时清理的演示用 Git 仓库",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s --setup              生成全部演示环境
  %(prog)s --setup --demo 1     仅生成 GIT_SMART_COMMIT 演示
  %(prog)s --setup --demo 2     仅生成 GIT_DAILY_SUMMARY 演示
  %(prog)s --show               查看状态 + 演示脚本
  %(prog)s --clean              删除所有演示环境
        """,
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--setup", action="store_true", help="生成演示环境")
    group.add_argument("--show", action="store_true", help="展示环境状态与演示脚本")
    group.add_argument("--clean", action="store_true", help="删除所有演示环境")
    parser.add_argument("--demo", type=int, choices=[1, 2], default=0,
                        help="指定演示编号 (1 或 2)，不指定则生成全部")

    args = parser.parse_args()

    if args.show:
        show_demo_status()
        return

    if args.clean:
        clean_demo_envs()
        return

    if args.setup:
        print(f"\n{C_BOLD}{'='*60}{C_RESET}")
        print(f"{C_BOLD}  Git SOP 演示环境生成{C_RESET}")
        print(f"{C_BOLD}{'='*60}{C_RESET}\n")

        do_all = args.demo == 0

        if do_all or args.demo == 1:
            setup_demo_smart_commit(DEMO1_DIR)
            print()

        if do_all or args.demo == 2:
            setup_demo_daily_summary(DEMO2_DIR)
            print()

        print(f"{C_BOLD}{'='*60}{C_RESET}")
        print(f"  {C_GREEN}演示环境生成完毕！{C_RESET}")
        print(f"  查看演示脚本: python tests/demo_env_generator.py --show")
        print(f"  清理环境:     python tests/demo_env_generator.py --clean")
        print(f"{C_BOLD}{'='*60}{C_RESET}\n")


if __name__ == "__main__":
    main()
