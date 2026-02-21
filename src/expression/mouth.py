"""
发声器官 — 监听主脑文本流，按句缓存，遇标点切断后送 TTS 引擎；
生成音频路径压入播放队列。
"""
from typing import AsyncIterator

# TODO: 正则按句切分，调用 Edge-TTS / FishAudio，入队 player
async def consume_text_stream(stream: AsyncIterator[str]) -> None:
    """消费 conscious 的文本流，按句 TTS 并压入播放队列。"""
    async for _ in stream:
        pass
