"""
耳朵 — 语音转文本 (STT)，供 Web/CLI/Telegram 使用。
统一经 llm-gateway 调用模型转写音频（LiteLLM + Langfuse）。
"""
import os
from src.core.logger import get_logger
from src.llm_gateway import (
    get_gateway_api_key,
    get_stt_model_name,
    speech_to_text as gateway_speech_to_text,
)

logger = get_logger(__name__)

# 扩展名 -> MIME，Gemini 支持 audio/webm, audio/mpeg, audio/wav 等
_MIME_MAP = {
    ".webm": "audio/webm",
    ".mp3": "audio/mpeg",
    ".wav": "audio/wav",
    ".m4a": "audio/mp4",
    ".ogg": "audio/ogg",
    ".flac": "audio/flac",
}


def _mime_for_filename(filename: str) -> str:
    ext = os.path.splitext(filename)[1].lower()
    return _MIME_MAP.get(ext, "audio/webm")


def speech_to_text(audio_bytes: bytes, filename: str = "audio.webm") -> str:
    """
    将音频转为文本，统一走 llm-gateway。
    支持常见格式：webm, mp3, wav, m4a, ogg 等。
    未配置 LITELLM_API_KEY 或调用失败时返回空字符串并打日志。
    """
    if not audio_bytes:
        return ""
    api_key = get_gateway_api_key()
    if not api_key:
        logger.warning("LITELLM_API_KEY 未配置，语音识别跳过")
        return ""
    mime = _mime_for_filename(filename)
    model_name = get_stt_model_name()
    if model_name.startswith("models/"):
        model_name = model_name.replace("models/", "", 1)

    try:
        text = gateway_speech_to_text(
            model_name=model_name,
            api_key=api_key,
            audio_bytes=audio_bytes,
            audio_mime=mime,
            trace_name="hearing_speech_to_text",
        )
        if text:
            logger.debug("[HEARING] 识别: %s", text[:80] + "..." if len(text) > 80 else text)
        return text
    except RuntimeError as e:
        logger.warning("llm-gateway 未就绪: %s", e)
        return ""
    except Exception as e:
        logger.warning("llm-gateway 语音转写异常: %s", e, exc_info=True)
        return ""
