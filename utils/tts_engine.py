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
import subprocess
import uuid

import edge_tts

logger = logging.getLogger(__name__)

# ── 配置 ──────────────────────────────────────────────────

VOICE = "zh-CN-XiaoxiaoNeural"  # 温暖女声

# ── 模块级状态 ────────────────────────────────────────────

_ready = False
_preload_lock = asyncio.Lock()


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
            communicate = edge_tts.Communicate("测试", VOICE)
            await communicate.save(output_path)
            _ready = True
        except Exception:
            _ready = False
        finally:
            try:
                os.remove(output_path)
            except OSError:
                pass


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
        communicate = edge_tts.Communicate(text, VOICE)
        await communicate.save(output_path)

        if not os.path.exists(output_path):
            return

        # ffplay 播放 MP3（-nodisp 不弹窗，-autoexit 播完退出）
        subprocess.run(
            ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", output_path],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=60,
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
