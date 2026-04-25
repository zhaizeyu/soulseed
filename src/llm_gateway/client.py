"""
llm-gateway — 统一封装 LiteLLM + Langfuse。
"""
import base64
import io
from typing import Any, AsyncIterator

from src.core.config_loader import get_config
from src.core.logger import get_logger

logger = get_logger(__name__)


def get_gateway_api_key() -> str:
    """统一获取网关 API Key。"""
    cfg = get_config()
    return str(cfg.get("LITELLM_API_KEY") or "").strip()


def get_gateway_api_base() -> str:
    """统一获取 OpenAI-compatible 网关 Base URL。"""
    cfg = get_config()
    return str(cfg.get("OPENAI_BASE_URL") or "").strip()


def get_chat_model_name() -> str:
    """统一获取聊天模型名。"""
    cfg = get_config()
    return str(cfg.get("CHAT_MODEL") or "deepseek-chat").strip()


def get_stt_model_name() -> str:
    """统一获取语音转写模型名。"""
    cfg = get_config()
    return str(cfg.get("VISION_TO_TEXT_MODEL") or cfg.get("CHAT_MODEL") or "deepseek-chat").strip()


def get_embedding_model_name() -> str:
    """统一获取嵌入模型名。"""
    cfg = get_config()
    return str(cfg.get("EMBEDDING_MODEL") or "text-embedding-3-small").strip()


def build_mem0_openai_config(*, llm_temperature: float, embedding_dims: int, vector_path: str) -> dict[str, Any]:
    """统一构建 Mem0 的 OpenAI-compatible 配置。"""
    api_key = get_gateway_api_key()
    api_base = get_gateway_api_base()
    return {
        "embedder": {
            "provider": "openai",
            "config": {
                "model": get_embedding_model_name(),
                "api_key": api_key,
                "openai_base_url": api_base,
                "embedding_dims": embedding_dims,
            },
        },
        "llm": {
            "provider": "openai",
            "config": {
                "model": get_chat_model_name(),
                "temperature": llm_temperature,
                "api_key": api_key,
                "openai_base_url": api_base,
            },
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "path": vector_path,
                "embedding_model_dims": embedding_dims,
                "on_disk": True,
            },
        },
    }


def _normalize_model_name(model_name: str) -> str:
    """未带 provider 前缀时统一为 openai/*（配合 OPENAI_BASE_URL）。"""
    raw = (model_name or "").strip()
    if raw.startswith("models/"):
        raw = raw.replace("models/", "", 1)
    if "/" in raw:
        return raw
    return f"openai/{raw or 'deepseek-chat'}"


def _litellm_callbacks_and_metadata(trace_name: str) -> tuple[list[str], dict[str, Any]]:
    """
    构建 Langfuse 回调与 metadata（强制开启）。

    约束：所有经 llm-gateway 的 LLM 调用都必须打到 Langfuse。
    若缺少 Langfuse 关键配置则直接报错，避免静默绕过观测。
    """
    cfg = get_config()
    pub = str(cfg.get("LANGFUSE_PUBLIC_KEY") or "").strip()
    sec = str(cfg.get("LANGFUSE_SECRET_KEY") or "").strip()
    host = str(cfg.get("LANGFUSE_HOST") or cfg.get("LANGFUSE_BASE_URL") or "").strip()
    missing: list[str] = []
    if not pub:
        missing.append("LANGFUSE_PUBLIC_KEY")
    if not sec:
        missing.append("LANGFUSE_SECRET_KEY")
    if not host:
        missing.append("LANGFUSE_BASE_URL(or LANGFUSE_HOST)")
    if missing:
        raise RuntimeError(
            "Langfuse 配置缺失，拒绝执行 LLM 调用。缺失项: " + ", ".join(missing)
        )
    try:
        import langfuse as _langfuse  # type: ignore
    except Exception as e:
        raise RuntimeError(
            "Langfuse SDK 不可用，拒绝执行 LLM 调用。请安装兼容版本：langfuse>=2.44,<3"
        ) from e
    if not hasattr(_langfuse, "version"):
        raise RuntimeError(
            "当前 Langfuse SDK 与 LiteLLM 不兼容（缺少 langfuse.version）。"
            "请安装兼容版本：langfuse>=2.44,<3"
        )

    metadata: dict[str, Any] = {"trace_name": trace_name}
    if cfg.get("langfuse_session_id"):
        metadata["session_id"] = str(cfg.get("langfuse_session_id"))
    if cfg.get("langfuse_user_id"):
        metadata["user_id"] = str(cfg.get("langfuse_user_id"))
    return ["langfuse"], metadata


def _pil_image_to_data_uri(image: Any, *, quality: int = 72) -> str | None:
    """把 PIL 图片转成 data URI，供 LiteLLM 多模态消息。"""
    try:
        from PIL import Image
    except Exception:
        return None
    if image is None or not isinstance(image, Image.Image):
        return None
    q = max(1, min(100, int(quality)))
    buf = io.BytesIO()
    image.convert("RGB").save(buf, format="JPEG", quality=q)
    b64 = base64.b64encode(buf.getvalue()).decode("ascii")
    return f"data:image/jpeg;base64,{b64}"


def _extract_delta_text(chunk: Any) -> str:
    """从 LiteLLM 流式 chunk 中提取文本。"""
    try:
        choices = getattr(chunk, "choices", None) or []
        if not choices:
            return ""
        delta = getattr(choices[0], "delta", None)
        if delta is None:
            return ""
        content = getattr(delta, "content", None)
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(str(item.get("text") or ""))
            return "".join(parts)
        return ""
    except Exception:
        return ""


def _is_truthy(val: Any, default: bool = False) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    return str(val).strip().lower() in {"1", "true", "yes", "on"}


def _apply_safety_overrides(kwargs: dict[str, Any], normalized_model: str) -> None:
    """
    安全策略覆盖：
    - 默认开启 `DISABLE_SENSITIVE_CHECK=true`，不做本地敏感词校验（项目内本就无该校验）。
    - 对 gemini provider 追加最宽松 safety_settings（BLOCK_NONE）。
    """
    cfg = get_config()
    disable_sensitive_check = _is_truthy(
        cfg.get("DISABLE_SENSITIVE_CHECK"), default=True
    )
    if not disable_sensitive_check:
        return
    if normalized_model.startswith("gemini/"):
        kwargs["safety_settings"] = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]


async def stream_chat(
    *,
    model_name: str,
    api_key: str,
    messages: list[dict[str, Any]],
    system_instruction: str | None = None,
    max_output_tokens: int = 8192,
    temperature: float | None = None,
    trace_name: str = "chat_stream",
) -> AsyncIterator[str]:
    """
    统一流式聊天接口（LiteLLM）。
    messages 使用 OpenAI 兼容格式，支持多模态 content 列表。
    """
    try:
        from litellm import acompletion
    except ImportError as e:
        raise RuntimeError("请安装 litellm: pip install litellm") from e

    callbacks, metadata = _litellm_callbacks_and_metadata(trace_name)
    final_messages = list(messages or [])
    if system_instruction:
        final_messages = [{"role": "system", "content": str(system_instruction)}] + final_messages

    api_base = get_gateway_api_base()

    normalized_model = _normalize_model_name(model_name)
    kwargs: dict[str, Any] = {
        "model": normalized_model,
        "messages": final_messages,
        "api_key": api_key,
        "stream": True,
        "max_tokens": max_output_tokens,
    }
    if api_base:
        kwargs["api_base"] = api_base
    if temperature is not None:
        kwargs["temperature"] = temperature
    kwargs["success_callback"] = callbacks
    kwargs["failure_callback"] = callbacks
    kwargs["metadata"] = metadata
    _apply_safety_overrides(kwargs, normalized_model)

    stream = await acompletion(**kwargs)
    async for chunk in stream:
        text = _extract_delta_text(chunk)
        if text:
            yield text


def speech_to_text(
    *,
    model_name: str,
    api_key: str,
    audio_bytes: bytes,
    audio_mime: str,
    trace_name: str = "speech_to_text",
) -> str:
    """统一语音转写接口（LiteLLM 多模态）。"""
    if not audio_bytes:
        return ""
    try:
        from litellm import completion
    except ImportError as e:
        raise RuntimeError("请安装 litellm: pip install litellm") from e

    b64_audio = base64.b64encode(audio_bytes).decode("ascii")
    callbacks, metadata = _litellm_callbacks_and_metadata(trace_name)
    api_base = get_gateway_api_base()

    normalized_model = _normalize_model_name(model_name)
    kwargs: dict[str, Any] = {
        "model": normalized_model,
        "api_key": api_key,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "将这段音频转写成文字，只输出转写结果。"},
                    {
                        "type": "input_audio",
                        "input_audio": {
                            "data": b64_audio,
                            "format": audio_mime.split("/")[-1],
                        },
                    },
                ],
            }
        ],
    }
    if api_base:
        kwargs["api_base"] = api_base
    kwargs["success_callback"] = callbacks
    kwargs["failure_callback"] = callbacks
    kwargs["metadata"] = metadata
    _apply_safety_overrides(kwargs, normalized_model)

    resp = completion(**kwargs)
    try:
        return str(resp.choices[0].message.content or "").strip()
    except Exception:
        return ""


def build_image_content_part(image: Any, *, quality: int = 72) -> dict[str, Any] | None:
    """把 PIL 图片封装为 OpenAI 兼容 image_url part。"""
    uri = _pil_image_to_data_uri(image, quality=quality)
    if not uri:
        return None
    return {"type": "image_url", "image_url": {"url": uri}}
