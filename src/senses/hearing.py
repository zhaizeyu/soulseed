"""
耳朵 — 麦克风录音控制、静音检测 (VAD)、语音转文本 (STT)。
集成 WebRTC VAD 或 Silero VAD；超过阈值触发录音，持续静音停止；
音频块送 Whisper API 返回识别文本。
"""
import asyncio
from typing import AsyncIterator

# TODO: 实现 VAD + 录音 + Whisper 调用
async def listen() -> AsyncIterator[str]:
    """监听用户语音，yield 识别出的文本。"""
    yield ""
    await asyncio.sleep(0)
