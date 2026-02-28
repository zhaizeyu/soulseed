"""
耳朵 — 语音转文本 (STT)，供 Web/CLI 使用。
使用 Google Gemini 多模态能力：上传音频后由 Gemini 转写为文字。
Web：前端录音后 POST 到 /api/speech-to-text，本模块调 Gemini 返回文本。
CLI：后续可接入 VAD + 本地录音，再调本模块。
"""
import os
import tempfile
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
    将音频转为文本，使用 Google Gemini 多模态（语音转写）。
    支持常见格式：webm, mp3, wav, m4a 等。
    未配置 GEMINI_API_KEY 或调用失败时返回空字符串并打日志。
    """
    if not audio_bytes:
        return ""
    api_key = (get_config().get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY 未配置，语音识别跳过")
        return ""
    mime = _mime_for_filename(filename)
    tmp_path = None
    try:
        import google.generativeai as genai
        genai.configure(api_key=api_key)
        with tempfile.NamedTemporaryFile(suffix=os.path.splitext(filename)[1] or ".webm", delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name
        uploaded = genai.upload_file(path=tmp_path, mime_type=mime)
        model_name = get_config().get("gemini_model") or get_config().get("GEMINI_MODEL") or "gemini-2.0-flash"
        if not model_name.startswith("models/"):
            model_name = f"models/{model_name}"
        model = genai.GenerativeModel(model_name=model_name)
        response = model.generate_content(
            ["将这段音频转写成文字，只输出转写结果，不要其他说明或标点以外的内容。", uploaded],
        )
        try:
            text = (response.text or "").strip()
        except (ValueError, AttributeError):
            # 无有效 Part 时（如 finish_reason=SAFETY 等）response.text 会抛错
            text = ""
        if text:
            logger.debug("[HEARING] 识别: %s", text[:80] + "..." if len(text) > 80 else text)
        return text
    except ImportError:
        logger.warning("未安装 google-generativeai，语音识别不可用。pip install google-generativeai")
        return ""
    except Exception as e:
        logger.warning("Gemini 语音转写异常: %s", e, exc_info=True)
        return ""
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
