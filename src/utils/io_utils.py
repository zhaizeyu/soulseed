"""
图片压缩、音频格式转换等本地 I/O 辅助函数（占位实现）。
"""
from pathlib import Path
from typing import Any


def compress_image(image: Any, max_size_kb: int = 500) -> bytes:
    """将图片压缩到指定大小以内，返回字节。"""
    return b""


def ensure_audio_format(path: Path, target_format: str = "wav") -> Path:
    """确保音频为 target_format，必要时转换并返回新路径。"""
    return path
