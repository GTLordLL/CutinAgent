"""TTS 语音播报引擎（Microsoft Edge TTS，云端推理）。

基于 edge-tts (Microsoft Edge 免费 TTS API)，云端推理，零本地开销。
原生 async/await，适配 REPL asyncio 事件循环。

用法:
    from utils.tts_engine import preload, speak_async, is_loaded

    # REPL 启动时（验证连通性）
    await preload()

    # 播报 Agent 回复（不阻塞事件循环）
    asyncio.create_task(speak_async("你好，我是CutinAgent。"))
"""

import asyncio
import logging
import os
import re
import subprocess
import uuid

import edge_tts

logger = logging.getLogger(__name__)

# ── 模块级状态 ────────────────────────────────────────────

_ready = False
_preload_lock = asyncio.Lock()
_main_loop: "asyncio.AbstractEventLoop | None" = None

# ── 播报队列（单消费者串行播放，避免音频重叠）──
_tts_queue: "asyncio.Queue[str] | None" = None
_consumer_task: "asyncio.Task | None" = None


def is_loaded() -> bool:
    """TTS 服务是否可用（连通性验证通过）。"""
    return _ready


async def preload() -> None:
    """验证 edge-tts API 连通性（在 async 上下文中 await 调用）。

    发送一次短合成请求验证 API 可达，设置 _ready 标志。
    锁保护，多次并发调用只执行一次连通检查。
    """
    global _ready
    if _ready:
        return

    async with _preload_lock:
        if _ready:
            return
        output_path = f"/tmp/tts_agent_precheck_{uuid.uuid4().hex[:8]}.mp3"
        try:
            communicate = edge_tts.Communicate("测试", "zh-CN-XiaoxiaoNeural")
            await communicate.save(output_path)
            _ready = True
        except Exception:
            _ready = False
        finally:
            try:
                os.remove(output_path)
            except OSError:
                pass


def _clean_markdown(text: str) -> str:
    """清洗 Markdown 符号，使 TTS 播报更自然。

    移除/替换常见的 Markdown 格式标记，保留纯文本语义内容。
    按顺序处理，避免清洗后的残留字符被后续规则误匹配。

    Args:
        text: 可能包含 Markdown 格式的原始文本。

    Returns:
        清洗后的纯文本。
    """
    # ── 第1层：反斜杠转义（必须在所有格式规则之前处理）──
    # 1. 反斜杠转义: \*, \[, \` 等 → 移除反斜杠
    text = re.sub(r'\\([\\`*_{}\[\]()#+\-.!|~])', r'\1', text)

    # ── 第2层：链接/图片（提取 alt/text，丢弃 URL）──
    # 2. 图片: ![alt](url) -> alt
    text = re.sub(r'!\[([^\]]*)\]\([^)]+\)', r'\1', text)
    # 3. 链接: [text](url) -> text
    text = re.sub(r'\[([^\]]*)\]\([^)]+\)', r'\1', text)

    # ── 第3层：代码（先处理多行代码块，再处理行内代码）──
    # 4. 围栏代码块: ```lang\n...\n``` -> 保留内容
    text = re.sub(r'```\w*\n(.*?)\n```', r'\1', text, flags=re.DOTALL)
    # 5. 行内代码: `code` -> code
    text = re.sub(r'`([^`]+)`', r'\1', text)

    # ── 第4层：内联格式（粗体/斜体/删除线）──
    # 6. 粗体: **text** -> text
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    # 7. 斜体: *text* -> text（非贪婪，避免跨段误匹配）
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    # 8. 粗体/斜体 (下划线): __text__ -> text
    text = re.sub(r'__([^_]+)__', r'\1', text)
    # 9. 删除线: ~~text~~ -> text
    text = re.sub(r'~~([^~]+)~~', r'\1', text)

    # ── 第5层：块级标记（行首符号）──
    # 10. 标题标记: # ## ### ... (行首)
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)
    # 11. 引用标记: > (行首)
    text = re.sub(r'^>\s+', '', text, flags=re.MULTILINE)
    # 12. 无序列表: - * + (行首)
    text = re.sub(r'^[\-\*\+]\s+', '', text, flags=re.MULTILINE)
    # 13. 有序列表: 1. 2. (行首)
    text = re.sub(r'^\d+\.\s+', '', text, flags=re.MULTILINE)
    # 14. 水平线: --- *** ___ (整行只有这些字符)
    text = re.sub(r'^[\-\*\_]{3,}\s*$', '', text, flags=re.MULTILINE)

    # ── 第6层：HTML 与表格 ──
    # 15. HTML 标签: <br>, <b>, </b> 等
    text = re.sub(r'<[^>]+>', '', text)
    # 16. 表格分隔行: |---| 等（整行只有 |:-- 字符，先处理避免留空行）
    text = re.sub(r'^[\|\s\-\:]+$', '', text, flags=re.MULTILINE)
    # 17. 表格竖线: 替换为空格
    text = re.sub(r'\|', ' ', text)

    # ── 第7层：空白清理 ──
    # 18. 清理多余空白
    text = re.sub(r'\n{3,}', '\n\n', text)
    text = re.sub(r' {2,}', ' ', text)

    return text.strip()


async def speak_async(text: str) -> None:
    """异步 TTS 播报入口。

    使用 edge_tts 云端合成 MP3 → ffplay 播放。
    异常静默降级，不影响 REPL 正常工作。

    Args:
        text: 要朗读的文本。
    """
    if not text or not text.strip():
        return

    output_path = f"/tmp/tts_agent_{uuid.uuid4().hex[:8]}.mp3"

    try:
        from repl.config_manager import get_config
        cfg = get_config()
        voice = cfg.get("tts_voice", "zh-CN-XiaoxiaoNeural")
        rate = cfg.get("tts_rate", "+0%")
        communicate = edge_tts.Communicate(text, voice, rate=rate)
        await communicate.save(output_path)

        if not os.path.exists(output_path):
            return

        # ffplay 播放 MP3（在线程池中运行，不阻塞事件循环）
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", output_path],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                timeout=60,
            )
        )

    except Exception:
        # TTS 失败不影响 REPL，静默降级
        logger.debug("TTS speak failed", exc_info=True)

    finally:
        try:
            if os.path.exists(output_path):
                os.remove(output_path)
        except OSError:
            pass


async def _tts_consumer() -> None:
    """后台消费者：从队列取出文本，逐个串行播报。

    阻塞在 queue.get()（空队列时零 CPU），
    await speak_async 时释放事件循环（ffplay 走 run_in_executor）。
    """
    while True:
        text = await _tts_queue.get()
        try:
            await speak_async(text)
        except Exception:
            pass
        finally:
            _tts_queue.task_done()


def _ensure_consumer() -> None:
    """确保消费者任务已启动（懒初始化，首次 tts_say 时触发）。"""
    global _tts_queue, _consumer_task, _main_loop
    if _consumer_task is None or _consumer_task.done():
        try:
            loop = asyncio.get_running_loop()
            _main_loop = loop
            _tts_queue = asyncio.Queue()
            _consumer_task = loop.create_task(_tts_consumer())
        except RuntimeError:
            pass  # Worker 线程无法创建 asyncio Task，交由 run_coroutine_threadsafe 路径处理


async def _enqueue_text(text: str) -> None:
    """入队播报文本（供 run_coroutine_threadsafe 从 worker 线程调度到主事件循环）。"""
    _ensure_consumer()
    await _tts_queue.put(text)


def tts_say(text: str) -> None:
    """如果 TTS 开启，将文本入队播报（不阻塞当前流程）。

    文本进入 asyncio.Queue，由后台单消费者串行播放，
    避免多次快速调用时音频重叠。

    支持从主线程（事件循环线程）和 worker 线程调用：
    - 主线程：直接 put_nowait 入队
    - Worker 线程：通过 asyncio.run_coroutine_threadsafe 调度到主事件循环入队

    Args:
        text: 要朗读的文本。
    """
    from repl.config_manager import get_config
    if get_config().get("tts_enabled", False) and text and text.strip():
        text = _clean_markdown(text.strip())
        if not text:
            return
        try:
            # 主线程路径：直接在事件循环线程操作
            asyncio.get_running_loop()
            _ensure_consumer()
            _tts_queue.put_nowait(text)
        except RuntimeError:
            # Worker 线程路径：调度到主事件循环
            if _main_loop and _main_loop.is_running():
                asyncio.run_coroutine_threadsafe(
                    _enqueue_text(text), _main_loop
                )
