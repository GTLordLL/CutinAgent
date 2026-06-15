"""演示 5：GIT_RELEASE_NOTES — Release Notes 生成。

场景：带版本 tag 的仓库，在两个 tag 之间有 10 条混合提交（feat/fix/refactor/docs/chore/test/security）。
- v0.1.0 到 v0.2.0: 10 条提交，覆盖 7 种 conventional commit 类型
- v0.2.0 之后: 2 条未打 tag 的提交（含重要修复）
"""

import os
import shutil

from tests.demo_utils import (
    C_CYAN, C_GREEN, C_RESET,
    date_days_ago, git_add_commit, git_init, run, write_file,
)


def setup_demo_release_notes(repo_dir):
    """搭建演示5仓库：带版本tag的仓库，tag间有10条提交可生成 Release Notes。"""
    print(f"  {C_CYAN}[演示5] 搭建 GIT_RELEASE_NOTES 演示环境 ...{C_RESET}")

    if os.path.isdir(repo_dir):
        shutil.rmtree(repo_dir)

    git_init(repo_dir)
    run(["git", "branch", "-M", "main"], cwd=repo_dir)

    # ====== v0.1.0 之前的初始提交 ======
    write_file(repo_dir, "README.md", """\
# NotificationCenter — 消息通知中心

可扩展的多渠道消息推送服务，支持短信、邮件、Webhook。
""")
    write_file(repo_dir, "src/__init__.py", "")
    write_file(repo_dir, "src/notifier.py", '''\
"""消息通知核心模块。"""
from typing import Optional


class Notification:
    def __init__(self, title: str, body: str, level: str = "info"):
        self.title = title
        self.body = body
        self.level = level


class Notifier:
    def __init__(self):
        self._channels: list = []

    def register_channel(self, channel):
        self._channels.append(channel)

    def send(self, notification: Notification) -> list[bool]:
        results = []
        for ch in self._channels:
            try:
                ch.deliver(notification)
                results.append(True)
            except Exception:
                results.append(False)
        return results
''')
    write_file(repo_dir, "requirements.txt", "requests==2.28.0\n")
    git_add_commit(repo_dir, "init: 初始化消息通知中心项目骨架",
                   date_str=date_days_ago(35))

    # ====== v0.1.0 tag（30天前）—— 第一个可用版本 ======
    run(["git", "tag", "v0.1.0"], cwd=repo_dir)

    # ====== v0.1.0 → v0.2.0：10 条提交，7 种类型 ======

    # 1. feat: 短信渠道
    write_file(repo_dir, "src/channels/__init__.py", "")
    write_file(repo_dir, "src/channels/sms.py", '''\
"""短信推送渠道。"""


class SMSChannel:
    def __init__(self, api_key: str, endpoint: str):
        self.api_key = api_key
        self.endpoint = endpoint

    def deliver(self, notification) -> bool:
        print(f"[SMS] 发送到手机: {notification.title}")
        return True
''')
    git_add_commit(repo_dir, "feat(channels): 实现短信推送渠道（SMSChannel）",
                   date_str=date_days_ago(28))

    # 2. feat: 邮件渠道
    write_file(repo_dir, "src/channels/email.py", '''\
"""邮件推送渠道。"""
import smtplib
from email.mime.text import MIMEText


class EmailChannel:
    def __init__(self, smtp_host: str, smtp_port: int = 587,
                 username: str = "", password: str = ""):
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    def deliver(self, notification) -> bool:
        msg = MIMEText(notification.body, "plain", "utf-8")
        msg["Subject"] = notification.title
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception:
            return False
''')
    git_add_commit(repo_dir, "feat(channels): 实现邮件推送渠道（EmailChannel）",
                   date_str=date_days_ago(26))

    # 3. fix: 修复多渠道批量发送失败时不继续的问题
    write_file(repo_dir, "src/notifier.py", '''\
"""消息通知核心模块。"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class Notification:
    def __init__(self, title: str, body: str, level: str = "info"):
        self.title = title
        self.body = body
        self.level = level


class Notifier:
    def __init__(self):
        self._channels: list = []

    def register_channel(self, channel):
        self._channels.append(channel)

    def send(self, notification: Notification) -> list[dict]:
        """发送通知到所有已注册渠道。单个渠道失败不影响其他渠道。"""
        results = []
        for ch in self._channels:
            try:
                ch.deliver(notification)
                results.append({"channel": type(ch).__name__, "status": "ok"})
            except Exception as e:
                logger.error(f"渠道 {type(ch).__name__} 发送失败: {e}")
                results.append({"channel": type(ch).__name__,
                                "status": "failed", "error": str(e)})
        return results
''')
    git_add_commit(repo_dir, "fix(notifier): 修复单渠道失败导致后续渠道被跳过的问题",
                   date_str=date_days_ago(24))

    # 4. refactor: 抽象 Channel 基类
    write_file(repo_dir, "src/channels/base.py", '''\
"""推送渠道抽象基类。"""
from abc import ABC, abstractmethod


class BaseChannel(ABC):
    """所有推送渠道的抽象基类。"""

    def __init__(self, name: str, retry: int = 3):
        self.name = name
        self.retry = retry

    @abstractmethod
    def deliver(self, notification) -> bool:
        """发送通知，返回是否成功。"""
        ...

    def send_with_retry(self, notification) -> bool:
        """带重试的发送。"""
        for attempt in range(self.retry):
            try:
                return self.deliver(notification)
            except Exception:
                if attempt == self.retry - 1:
                    raise
        return False
''')
    # 更新 sms.py 继承 BaseChannel
    write_file(repo_dir, "src/channels/sms.py", '''\
"""短信推送渠道。"""
from src.channels.base import BaseChannel


class SMSChannel(BaseChannel):
    def __init__(self, api_key: str, endpoint: str):
        super().__init__(name="SMS", retry=2)
        self.api_key = api_key
        self.endpoint = endpoint

    def deliver(self, notification) -> bool:
        print(f"[SMS] 发送到手机: {notification.title}")
        return True
''')
    # 更新 email.py 继承 BaseChannel
    write_file(repo_dir, "src/channels/email.py", '''\
"""邮件推送渠道。"""
import smtplib
from email.mime.text import MIMEText
from src.channels.base import BaseChannel


class EmailChannel(BaseChannel):
    def __init__(self, smtp_host: str, smtp_port: int = 587,
                 username: str = "", password: str = ""):
        super().__init__(name="Email", retry=3)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username
        self.password = password

    def deliver(self, notification) -> bool:
        msg = MIMEText(notification.body, "plain", "utf-8")
        msg["Subject"] = notification.title
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception:
            return False
''')
    git_add_commit(repo_dir, "refactor(channels): 抽取 BaseChannel 抽象基类，统一重试逻辑",
                   date_str=date_days_ago(22))

    # 5. docs: 更新 README
    write_file(repo_dir, "README.md", """\
# NotificationCenter — 消息通知中心

可扩展的多渠道消息推送服务，支持短信、邮件、Webhook。

## 已支持渠道

| 渠道 | 模块 | 状态 |
|------|------|------|
| 短信 | `src/channels/sms.py` | ✅ 可用 |
| 邮件 | `src/channels/email.py` | ✅ 可用 |

## 快速开始

```python
from src.notifier import Notifier, Notification
from src.channels.sms import SMSChannel

notifier = Notifier()
notifier.register_channel(SMSChannel(api_key="xxx", endpoint="https://..."))
notifier.send(Notification(title="告警", body="CPU > 90%", level="warning"))
```

## 渠道开发

继承 `src.channels.base.BaseChannel`，实现 `deliver()` 方法即可:
```python
from src.channels.base import BaseChannel

class WebhookChannel(BaseChannel):
    def deliver(self, notification) -> bool:
        # 发送 HTTP POST 到 webhook URL
        ...
```
""")
    git_add_commit(repo_dir, "docs(readme): 补充渠道列表、快速开始和渠道开发指南",
                   date_str=date_days_ago(20))

    # 6. test: 添加 notifier 单元测试
    write_file(repo_dir, "tests/__init__.py", "")
    write_file(repo_dir, "tests/test_notifier.py", '''\
"""通知核心模块单元测试。"""
import pytest
from src.notifier import Notifier, Notification
from src.channels.base import BaseChannel


class FakeChannel(BaseChannel):
    """测试用伪渠道。"""
    def __init__(self, should_fail=False):
        super().__init__(name="Fake")
        self.should_fail = should_fail
        self.delivered = []

    def deliver(self, notification) -> bool:
        if self.should_fail:
            raise RuntimeError("模拟发送失败")
        self.delivered.append(notification)
        return True


class TestNotifier:
    def test_send_single_channel(self):
        n = Notifier()
        fake = FakeChannel()
        n.register_channel(fake)
        notif = Notification("test", "hello")
        results = n.send(notif)
        assert len(results) == 1
        assert results[0]["status"] == "ok"
        assert len(fake.delivered) == 1

    def test_send_partial_failure(self):
        n = Notifier()
        n.register_channel(FakeChannel())
        n.register_channel(FakeChannel(should_fail=True))
        n.register_channel(FakeChannel())
        notif = Notification("test", "partial")
        results = n.send(notif)
        assert results[0]["status"] == "ok"
        assert results[1]["status"] == "failed"
        assert results[2]["status"] == "ok"

    def test_send_no_channels(self):
        n = Notifier()
        results = n.send(Notification("test", "none"))
        assert results == []
''')
    git_add_commit(repo_dir, "test(notifier): 添加推送核心模块单元测试（含部分失败场景）",
                   date_str=date_days_ago(18))

    # 7. feat: Webhook 渠道
    write_file(repo_dir, "src/channels/webhook.py", '''\
"""Webhook 推送渠道。"""
import requests
from src.channels.base import BaseChannel


class WebhookChannel(BaseChannel):
    def __init__(self, url: str, secret: str = "",
                 timeout: int = 10):
        super().__init__(name="Webhook", retry=2)
        self.url = url
        self.secret = secret
        self.timeout = timeout

    def deliver(self, notification) -> bool:
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Webhook-Secret"] = self.secret
        payload = {
            "title": notification.title,
            "body": notification.body,
            "level": notification.level,
        }
        resp = requests.post(
            self.url, json=payload, headers=headers,
            timeout=self.timeout
        )
        return resp.status_code == 200
''')
    git_add_commit(repo_dir, "feat(channels): 实现 Webhook 推送渠道（含签名验证）",
                   date_str=date_days_ago(15))

    # 8. chore: 更新依赖
    write_file(repo_dir, "requirements.txt", """\
requests==2.31.0
pytest==8.2.0
pytest-cov==5.0.0
black==24.4.0
""")
    git_add_commit(repo_dir, "chore(deps): 更新 requests 到 2.31 并添加 pytest-cov 和 black",
                   date_str=date_days_ago(12))

    # 9. fix: 修复 Webhook 超时不拦截的问题
    write_file(repo_dir, "src/channels/webhook.py", '''\
"""Webhook 推送渠道。"""
import requests
from src.channels.base import BaseChannel


class WebhookChannel(BaseChannel):
    def __init__(self, url: str, secret: str = "",
                 timeout: int = 10):
        super().__init__(name="Webhook", retry=2)
        self.url = url
        self.secret = secret
        self.timeout = timeout

    def deliver(self, notification) -> bool:
        headers = {"Content-Type": "application/json"}
        if self.secret:
            headers["X-Webhook-Secret"] = self.secret
        payload = {
            "title": notification.title,
            "body": notification.body,
            "level": notification.level,
        }
        try:
            resp = requests.post(
                self.url, json=payload, headers=headers,
                timeout=self.timeout
            )
            return resp.status_code == 200
        except requests.exceptions.Timeout:
            return False
        except requests.exceptions.ConnectionError:
            return False
''')
    git_add_commit(repo_dir, "fix(webhook): 捕获 Timeout 和 ConnectionError 防止渠道崩溃",
                   date_str=date_days_ago(10))

    # 10. security: 邮件密码脱敏
    write_file(repo_dir, "src/channels/email.py", '''\
"""邮件推送渠道（凭据安全增强）。"""
import os
import smtplib
from email.mime.text import MIMEText
from src.channels.base import BaseChannel


class EmailChannel(BaseChannel):
    def __init__(self, smtp_host: str, smtp_port: int = 587,
                 username: str = "", password: str = ""):
        super().__init__(name="Email", retry=3)
        self.smtp_host = smtp_host
        self.smtp_port = smtp_port
        self.username = username or os.getenv("NOTIFY_SMTP_USER", "")
        self.password = password or os.getenv("NOTIFY_SMTP_PASS", "")

    def deliver(self, notification) -> bool:
        msg = MIMEText(notification.body, "plain", "utf-8")
        msg["Subject"] = notification.title
        try:
            with smtplib.SMTP(self.smtp_host, self.smtp_port) as server:
                server.starttls()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(msg)
            return True
        except Exception:
            return False
''')
    git_add_commit(repo_dir, "security(email): 支持从环境变量读取SMTP凭据，避免硬编码密码",
                   date_str=date_days_ago(8))

    # ====== v0.2.0 tag（7天前）—— 第二个版本 ======
    run(["git", "tag", "v0.2.0"], cwd=repo_dir)

    # ====== v0.2.0 之后：2 条提交（未打 tag） ======

    # 11. fix: 修复 Notification level 枚举
    write_file(repo_dir, "src/notifier.py", '''\
"""消息通知核心模块。"""
import logging
from enum import Enum

logger = logging.getLogger(__name__)


class Level(str, Enum):
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class Notification:
    def __init__(self, title: str, body: str, level: Level = Level.INFO):
        self.title = title
        self.body = body
        self.level = level.value if isinstance(level, Level) else level


class Notifier:
    def __init__(self):
        self._channels: list = []

    def register_channel(self, channel):
        self._channels.append(channel)

    def send(self, notification: Notification) -> list[dict]:
        """发送通知到所有已注册渠道。单个渠道失败不影响其他渠道。"""
        results = []
        for ch in self._channels:
            try:
                ch.deliver(notification)
                results.append({"channel": type(ch).__name__, "status": "ok"})
            except Exception as e:
                logger.error(f"渠道 {type(ch).__name__} 发送失败: {e}")
                results.append({"channel": type(ch).__name__,
                                "status": "failed", "error": str(e)})
        return results
''')
    git_add_commit(repo_dir, "fix(notifier): 将通知级别改为 Level 枚举，防止非法 level 值",
                   date_str=date_days_ago(3))

    # 12. feat: 添加通知模板
    write_file(repo_dir, "src/templates.py", '''\
"""通知消息模板引擎。"""
from string import Template


class TemplateEngine:
    """基于 string.Template 的简单模板引擎。"""

    def __init__(self):
        self._templates: dict[str, Template] = {}

    def register(self, name: str, template_str: str):
        self._templates[name] = Template(template_str)

    def render(self, name: str, **kwargs) -> str:
        if name not in self._templates:
            raise KeyError(f"模板 '{name}' 不存在")
        return self._templates[name].safe_substitute(**kwargs)


# 内置告警模板
DEFAULT_TEMPLATES = {
    "cpu_alert": Template(
        "[$hostname] CPU 使用率 $cpu_pct%，阈值 $threshold%"
    ),
    "deploy_notify": Template(
        "服务 $service 已部署到 $env 环境，版本 $version"
    ),
}
''')
    git_add_commit(repo_dir, "feat(templates): 添加通知消息模板引擎和内置告警模板",
                   date_str=date_days_ago(1))

    # 回到 main
    run(["git", "checkout", "main"], cwd=repo_dir)

    print(f"         {C_GREEN}仓库就绪{C_RESET}: 12 条提交 + 2 个 tag")
    print(f"           v0.1.0 → v0.2.0: 10 条提交（feat×3 / fix×2 / refactor×1 / docs×1 / test×1 / chore×1 / security×1）")
    print(f"           v0.2.0 → HEAD:     2 条提交（fix×1 / feat×1）")
    print(f"           用法: get_git_log(from_tag='v0.1.0', to_tag='v0.2.0')")
