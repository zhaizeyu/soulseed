"""
嘴巴 — 将文本合成为语音，供 Web 播报「说的话」等。
使用 Edge-TTS，音色由 config 的 tts_voice 指定（如 zh-CN-XiaoxiaoNeural）。
"""
from src.core.config_loader import get_config
from src.core.logger import get_logger

logger = get_logger(__name__)


async def text_to_speech_async(text: str) -> bytes:
    """
    将文本合成为语音，返回 mp3 字节。
    未配置 tts_voice 或调用失败时返回空 bytes。
    """
    text = (text or "").strip()
    if not text:
        return b""
    voice = (get_config().get("tts_voice") or "zh-CN-XiaoxiaoNeural").strip()
    try:
        import edge_tts
        communicate = edge_tts.Communicate(text, voice)
        chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk.get("type") == "audio" and chunk.get("data"):
                chunks.append(chunk["data"])
        return b"".join(chunks) if chunks else b""
    except ImportError:
        logger.warning("未安装 edge-tts，TTS 不可用。pip install edge-tts")
        return b""
    except Exception as e:
        logger.warning("Edge-TTS 合成异常: %s", e, exc_info=True)
        return b""
