#!/usr/bin/env python3
"""TTS 语音参数调节测试工具。

交互式调节 voice / rate / pitch / volume，实时试听效果。
需要: edge-tts, ffplay
用法: python tests/test_tts_tuning.py
"""

import asyncio
import subprocess
import uuid

import edge_tts

# ── 测试文本 ────────────────────────────────────────────────
TEST_TEXT = "你好，我是CutinAgent，一个基于SOP驱动的智能助手。有什么可以帮助你的吗？"

# ── 可用中文语音 ─────────────────────────────────────────────
ZH_VOICES = [
    ("zh-CN-XiaoxiaoNeural", "Female", "标准女声"),
    ("zh-CN-XiaoyiNeural", "Female", "轻柔女声"),
    ("zh-CN-YunjianNeural", "Male", "标准男声"),
    ("zh-CN-YunxiNeural", "Male", "活泼男声"),
    ("zh-CN-YunxiaNeural", "Male", "温和男声"),
    ("zh-CN-YunyangNeural", "Male", "沉稳男声"),
    ("zh-CN-liaoning-XiaobeiNeural", "Female", "东北方言"),
    ("zh-CN-shaanxi-XiaoniNeural", "Female", "陕西方言"),
]


async def play_tts(text: str, voice: str, rate: str, pitch: str, volume: str) -> float:
    """合成并播放，返回耗时（秒）。"""
    output_path = f"/tmp/tts_test_{uuid.uuid4().hex[:8]}.mp3"

    try:
        communicate = edge_tts.Communicate(
            text, voice,
            rate=rate,
            pitch=pitch,
            volume=volume,
        )
        await communicate.save(output_path)

        # 在线程池播放，不阻塞事件循环
        loop = asyncio.get_running_loop()
        await loop.run_in_executor(
            None,
            lambda: subprocess.run(
                ["ffplay", "-nodisp", "-autoexit", "-loglevel", "quiet", output_path],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
            )
        )
    finally:
        import os
        try:
            os.remove(output_path)
        except OSError:
            pass


def show_presets():
    """显示当前参数 + 推荐预设。"""
    print()
    print("  Voice 列表:")
    for i, (vid, gender, desc) in enumerate(ZH_VOICES, 1):
        print(f"    {i}. {vid} ({gender}, {desc})")

    print()
    print("  参数格式:")
    print("    rate   : 语速,  如 +0%, -20%, +30%   (范围 -50% ~ +100%)")
    print("    pitch  : 音调,  如 +0Hz, -10Hz, +15Hz (范围 -50Hz ~ +50Hz)")
    print("    volume : 音量,  如 +0%, -30%, +50%   (范围 -100% ~ +100%)")
    print()
    print("  推荐预设:")
    print("    默认   : voice=1  rate=+0%  pitch=+0Hz  volume=+0%")
    print("    快速   : voice=1  rate=+20%  pitch=+0Hz  volume=+0%")
    print("    沉稳   : voice=6  rate=-10%  pitch=-5Hz  volume=+0%")
    print("    活泼   : voice=4  rate=+15%  pitch=+10Hz  volume=+10%")


def parse_voice_input(s: str) -> str:
    """解析 voice 输入：数字 1-8 或完整语音名。"""
    s = s.strip()
    if s.isdigit():
        idx = int(s) - 1
        if 0 <= idx < len(ZH_VOICES):
            return ZH_VOICES[idx][0]
    if s and any(s == v[0] for v in ZH_VOICES):
        return s
    return ""


async def main():
    print("=" * 62)
    print("  TTS 语音参数调节测试")
    print("=" * 62)
    print(f"  测试文本: {TEST_TEXT}")

    # 默认参数
    voice = ZH_VOICES[0][0]  # Xiaoxiao
    rate = "+0%"
    pitch = "+0Hz"
    volume = "+0%"

    show_presets()

    while True:
        print("\n" + "-" * 62)
        print(f"  当前参数: voice={voice}  rate={rate}  pitch={pitch}  volume={volume}")
        print(f"  [p=播放  v=选语音  r=改语速  h=改音调  o=改音量  q=退出]")
        print("-" * 62)

        cmd = input("  > ").strip().lower()

        if cmd == "q":
            print("  再见！")
            break

        if cmd == "p":
            print(f"  合成并播放中... ({voice}, rate={rate}, pitch={pitch}, volume={volume})")
            await play_tts(TEST_TEXT, voice, rate, pitch, volume)
            print("  播放完毕。")
            continue

        if cmd == "v":
            print("  输入语音编号 (1-8) 或完整语音名:")
            for i, (vid, gender, desc) in enumerate(ZH_VOICES, 1):
                print(f"    {i}. {vid} ({desc})")
            v_input = input("  语音 > ").strip()
            parsed = parse_voice_input(v_input)
            if parsed:
                voice = parsed
                print(f"  已设置: {voice}")
            else:
                print("  无效输入，保持原设置。")
            continue

        if cmd in ("r", "h", "o"):
            param = {"r": ("rate", "语速"), "h": ("pitch", "音调"), "o": ("volume", "音量")}[cmd]
            key, label = param
            current = {"rate": rate, "pitch": pitch, "volume": volume}[key]
            unit = "%" if key != "pitch" else "Hz"
            print(f"  当前{label}: {current}")
            print(f"  输入新值 (如 +10{unit}, -20{unit}):")
            val = input(f"  {label} > ").strip()
            if val:
                if key == "rate":
                    rate = val
                elif key == "pitch":
                    pitch = val
                else:
                    volume = val
                print(f"  已设置 {label}: {val}")
            continue

        print(f"  未知命令: {cmd}")
        print("  p=播放  v=选语音  r=改语速  h=改音调  o=改音量  q=退出")


if __name__ == "__main__":
    asyncio.run(main())
