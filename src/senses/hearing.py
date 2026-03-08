"""
耳朵 — 语音转文本 (STT)，供 Web/CLI/Telegram 使用。
使用 Google Gemini（google-genai）多模态能力：上传音频后由 Gemini 转写为文字。
"""
import os
from src.core.config_loader import get_config
from src.core.logger import get_logger

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
    将音频转为文本，使用 Google Gemini（google-genai）多模态语音转写。
    支持常见格式：webm, mp3, wav, m4a, ogg 等。
    未配置 GEMINI_API_KEY 或调用失败时返回空字符串并打日志。
    """
    if not audio_bytes:
        return ""
    api_key = (get_config().get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY 未配置，语音识别跳过")
        return ""
    mime = _mime_for_filename(filename)
    model_name = (
        get_config().get("gemini_model") or get_config().get("GEMINI_MODEL") or "gemini-2.0-flash"
    ).strip()
    if model_name.startswith("models/"):
        model_name = model_name.replace("models/", "", 1)

    try:
        from google import genai
        from google.genai import types
    except ImportError:
        logger.warning("未安装 google-genai，语音识别不可用。pip install google-genai")
        return ""

    try:
        client = genai.Client(api_key=api_key)
        contents = [
            types.Part.from_text(
                text="将这段音频转写成文字，只输出转写结果，不要其他说明或标点以外的内容。"
            ),
            types.Part.from_bytes(data=audio_bytes, mime_type=mime),
        ]
        response = client.models.generate_content(
            model=model_name,
            contents=contents,
        )
        text = (getattr(response, "text", None) or "").strip()
        if text:
            logger.debug("[HEARING] 识别: %s", text[:80] + "..." if len(text) > 80 else text)
        return text
    except Exception as e:
        logger.warning("Gemini 语音转写异常: %s", e, exc_info=True)
        return ""
