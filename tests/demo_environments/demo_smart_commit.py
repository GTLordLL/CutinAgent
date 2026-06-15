"""演示 1：GIT_SMART_COMMIT — 智能提交。

场景：初始项目 + 混合变更（修改/新增/删除）。
"""

import os
import shutil

from tests.demo_utils import (
    C_BOLD, C_CYAN, C_GREEN, C_MAGENTA, C_RESET, C_YELLOW,
    git_add_commit, git_init, write_file,
)


def setup_demo_smart_commit(repo_dir):
    """搭建演示1仓库：初始项目 + 混合变更（修改/新增/删除）。"""
    print(f"  {C_CYAN}[演示1] 搭建 GIT_SMART_COMMIT 演示环境 ...{C_RESET}")

    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)

    git_init(repo_dir)

    # -- 初始提交 --
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

    # -- 制造混合变更 --
    write_file(repo_dir, "src/api/handler.py", '''\
"""HTTP 请求处理模块（含超时重试与精细化异常处理）。"""

import time
import logging
from typing import Optional

logger = logging.getLogger(__name__)


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
            time.sleep(1 * (attempt + 1))
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
    return type("Response", (), {
        "json": lambda: {"data": []},
        "status_code": 200,
    })()
''')

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

    os.remove(os.path.join(repo_dir, "src/models/user.py"))
    models_dir = os.path.join(repo_dir, "src/models")
    if os.path.isdir(models_dir) and not os.listdir(models_dir):
        os.rmdir(models_dir)

    write_file(repo_dir, "README.md", '''\
# MyShop API Client v0.2

一个健壮的电商 API 客户端库，支持用户管理、订单查询和数据缓存。

## 功能

- 获取用户资料（含超时重试与精细化异常处理）
- 查询订单列表（支持分页）
- LRU 内存缓存，减少重复 API 调用
- 自定义异常类：`RequestTimeout`, `APIError`

## 快速开始

```python
from src.api.handler import fetch_user_profile
from src.utils.cache import lru_cache

@lru_cache(maxsize=64, ttl=120)
def get_user_cached(user_id):
    return fetch_user_profile(user_id)

user = get_user_cached(1)
print(user)
```
''')

    print(f"         {C_GREEN}变更就绪{C_RESET}: 修改 2 个文件, 新增 1 个文件, 删除 1 个文件")
