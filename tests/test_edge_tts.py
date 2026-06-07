#!/usr/bin/env python3
"""edge-tts 语音播报 Demo（Microsoft Edge 免费 TTS API）。

测试中文语音合成质量与长文本推理速度，评估替代 PaddleSpeech 的可行性。

特点：
  - 云端推理，无需本地模型加载，零显存占用
  - 首次调用即热路径（无懒加载）
  - 原生 async，天然适配 REPL asyncio 事件循环
  - 中文语音选择丰富（Xiaoxiao 女声、Yunxi 男声等）

用法：
    source .venv/bin/activate
    python tests/test_edge_tts.py

若网络不通，可设置代理：export HTTP_PROXY=http://127.0.0.1:7897
"""

import asyncio
import os
import subprocess
import sys
import time
import uuid

import edge_tts

# ── 配置 ──────────────────────────────────────────────────

VOICE_FEMALE = "zh-CN-XiaoxiaoNeural"    # 温暖女声（新闻/小说）
VOICE_MALE = "zh-CN-YunxiNeural"         # 阳光男声（小说）
VOICE_PRO = "zh-CN-YunyangNeural"        # 专业男声（新闻）

OUTPUT_DIR = "/tmp"

# ── 核心函数 ──────────────────────────────────────────────

async def synthesize(text: str, voice: str, output_path: str) -> float:
    """合成语音并返回耗时（秒）。"""
    t0 = time.time()
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(output_path)
    return time.time() - t0


def play_audio(path: str) -> None:
    """播放 MP3 音频（edge-tts 返回 MPEG 格式，非 WAV）。"""
    if not os.path.exists(path):
        print(f"  [WARN] 文件不存在: {path}")
        return
    subprocess.run(
        ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", path],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        timeout=60,
    )


# ── 测试用例 ──────────────────────────────────────────────

async def test_basic():
    """Test 1: 基础中文短句合成。"""
    print("\n" + "=" * 60)
    print("  Test 1: 基础中文短句")
    print("=" * 60)

    texts = [
        "你好，我是CutinAgent，一个智能编程助手。",
        "有什么我可以帮助你的吗？",
    ]

    for i, text in enumerate(texts):
        output_path = f"{OUTPUT_DIR}/edge_demo_{i}.mp3"
        print(f"\n  [{i+1}] 输入: {text}")
        elapsed = await synthesize(text, VOICE_FEMALE, output_path)
        print(f"      耗时: {elapsed:.2f}s")
        print(f"      输出: {output_path}")


async def test_long_text():
    """Test 2: 长文本合成（模拟 Agent 实际回复长度）。"""
    print("\n" + "=" * 60)
    print("  Test 2: 长文本合成（模拟 Agent 回复）")
    print("=" * 60)

    long_texts = [
        # ~60 字：模拟简短回复
        "根据您的请求，我已经完成了对Git仓库状态的检查。"
        "当前分支为main，共有3个文件被修改，2个文件新增。"
        "所有变更已暂存，等待您的提交确认。",
        # ~120 字：模拟详细回复
        "根据您的请求，我已经完成了以下操作："
        "第一，检查了当前Git仓库的状态，发现main分支上有5个未提交的文件变更，"
        "其中包括2个新增文件和3个修改文件。"
        "第二，分析了代码变更的具体内容，主要是对用户认证模块的重构，"
        "将原有的session认证方式改为JWT token认证，提高了系统的可扩展性。"
        "第三，已按照约定式提交规范生成了提交信息，格式为type(scope): description。"
        "现在等待您的确认，是否需要我继续执行git commit操作？",
        # ~250 字：模拟完整报告
        "好的，我已经帮您完成了代码仓库的全面分析，下面是详细报告。"
        "首先看提交历史方面，过去一周共有23次提交，其中您个人贡献了15次，"
        "主要集中在用户认证模块和API接口的重构上。提交信息总体规范，"
        "但有3次提交使用了较模糊的描述，建议后续改进。"
        "其次看代码变更方面，共有12个文件被修改，新增代码约850行，删除约320行。"
        "核心变更是将原有的基于Session的用户认证机制升级为JWT Token方案，"
        "同时新增了Token自动刷新中间件，提升了系统的安全性和用户体验。"
        "另外，API接口层也做了相应的适配，所有需要认证的端点现在统一从"
        "Authorization头中读取Bearer Token，不再依赖Cookie中的Session ID。"
        "测试覆盖方面，新增了15个单元测试用例，覆盖了Token生成、验证、刷新"
        "以及过期处理等关键场景，当前测试通过率为百分之百。"
        "潜在风险方面，旧的Session认证代码尚未清理，建议在确认新方案稳定运行"
        "两周后进行移除，届时需要同步更新部署文档和相关配置。"
        "以上是完整的分析报告，请问您需要我针对某个方面做更深入的说明吗？",
    ]

    for i, text in enumerate(long_texts):
        output_path = f"{OUTPUT_DIR}/edge_long_{i}.mp3"
        print(f"\n  [{chr(ord('A')+i)}] 文本长度: {len(text)} 字符")
        print(f"      内容: {text[:80]}...")
        elapsed = await synthesize(text, VOICE_FEMALE, output_path)
        rate = len(text) / elapsed
        print(f"      耗时: {elapsed:.2f}s  |  速率: {rate:.0f} 字/秒")


async def test_voices():
    """Test 3: 不同音色对比。"""
    print("\n" + "=" * 60)
    print("  Test 3: 音色对比")
    print("=" * 60)

    text = "你好，我是CutinAgent智能助手，很高兴为您服务。"
    voices = [
        ("Xiaoxiao (温暖女声)", VOICE_FEMALE),
        ("Yunxi (阳光男声)", VOICE_MALE),
        ("Yunyang (专业男声)", VOICE_PRO),
    ]

    for i, (label, voice) in enumerate(voices):
        output_path = f"{OUTPUT_DIR}/edge_voice_{i}.mp3"
        print(f"\n  [{i+1}] {label}")
        print(f"      输入: {text}")
        elapsed = await synthesize(text, voice, output_path)
        print(f"      耗时: {elapsed:.2f}s")


async def test_concurrent():
    """Test 4: 并发合成（模拟连续对话场景）。"""
    print("\n" + "=" * 60)
    print("  Test 4: 连续合成性能")
    print("=" * 60)

    texts = [
        "正在分析您的请求。",
        "已找到3个匹配的SOP。",
        "正在执行Git提交操作。",
        "提交成功，Commit ID为abc123。",
        "还有什么可以帮您的吗？",
    ]

    times = []
    for i, text in enumerate(texts):
        output_path = f"{OUTPUT_DIR}/edge_seq_{i}.mp3"
        t0 = time.time()
        await synthesize(text, VOICE_FEMALE, output_path)
        elapsed = time.time() - t0
        times.append(elapsed)
        print(f"  [{i+1}] \"{text}\" → {elapsed:.2f}s")

    avg = sum(times) / len(times)
    print(f"\n  平均: {avg:.2f}s  |  最短: {min(times):.2f}s  |  最长: {max(times):.2f}s")


async def test_audio_quality(play: bool = False):
    """Test 5: 试听（可选）。"""
    print("\n" + "=" * 60)
    print("  Test 5: 试听样本")
    print("=" * 60)

    text = (
        "您的Git仓库当前状态良好，所有测试用例已通过，"
        "代码覆盖率达到百分之八十五，可以准备提交了。"
    )
    output_path = f"{OUTPUT_DIR}/edge_preview.mp3"
    print(f"\n  文本: {text}")
    elapsed = await synthesize(text, VOICE_FEMALE, output_path)
    print(f"  耗时: {elapsed:.2f}s")
    print(f"  输出: {output_path}")

    if play:
        print("  正在播放...")
        play_audio(output_path)
        print("  播放完成。")


# ── 主入口 ────────────────────────────────────────────────

async def main():
    print("=" * 60)
    print("  CutinAgent — edge-tts Demo")
    print("=" * 60)
    print(f"  引擎: Microsoft Edge TTS API (免费)")
    print(f"  默认音色: {VOICE_FEMALE}")
    print()

    # 先做一次预热（检查网络连通性 + 建立连接）
    print("[预热] 检查 API 连通性...")
    try:
        warm_path = f"{OUTPUT_DIR}/edge_warmup.mp3"
        t0 = time.time()
        await synthesize("测试连接", VOICE_FEMALE, warm_path)
        print(f"        连接正常，预热耗时: {time.time()-t0:.2f}s")
        os.remove(warm_path)
    except Exception as e:
        print(f"[FATAL] 无法连接 edge-tts API: {e}")
        print("请检查网络连接或设置 HTTP_PROXY 代理。")
        return

    tests = [
        ("基础短句", test_basic),
        ("长文本", test_long_text),
        ("音色对比", test_voices),
        ("连续合成", test_concurrent),
        ("试听", lambda: test_audio_quality(play=True)),
    ]

    for name, fn in tests:
        try:
            await fn()
        except Exception as e:
            print(f"\n  [FAIL] {name}: {e}")
            import traceback
            traceback.print_exc()


    # 清理
    print(f"\n  生成文件: {OUTPUT_DIR}/edge_*.mp3")
    import glob
    for f in sorted(glob.glob(f"{OUTPUT_DIR}/edge_*.mp3")):
        size_kb = os.path.getsize(f) / 1024
        print(f"    {f} ({size_kb:.1f} KB)")

    print("\n" + "=" * 60)
    print("  Demo 完成！")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(main())
