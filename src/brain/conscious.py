"""
主脑 — 通过 llm-gateway 统一调用大模型（LiteLLM + Langfuse）。
处理对话会话、多模态历史与系统提示词注入。
"""
import json
from pathlib import Path
from typing import Any, AsyncIterator

from src.core.config_loader import get_config
from src.core.logger import get_logger, get_log_path
from src.llm_gateway import (
    build_image_content_part,
    get_chat_model_name,
    get_gateway_api_key,
    stream_chat,
)
from src.brain.prompt_assembler import build_messages, load_system_prompt

logger = get_logger(__name__)
_PROJECT_ROOT = Path(__file__).resolve().parents[2]

def _load_history_image_to_part(image_path: str) -> dict[str, Any] | None:
    """从历史图片路径（相对项目根）加载并转为 image_url part；失败返回 None。"""
    if not (image_path or "").strip():
        return None
    path = _PROJECT_ROOT / image_path
    if not path.exists():
        return None
    try:
        from PIL import Image

        img = Image.open(path).convert("RGB")
        return _vision_image_to_part(img)
    except Exception as e:
        logger.debug("加载历史图片失败 %s: %s", path, e)
        return None


def _vision_image_to_part(vision_image: Any, *, quality: int | None = None) -> dict[str, Any] | None:
    """将 PIL.Image 转为 OpenAI 兼容 image_url part。"""
    if vision_image is None:
        return None
    try:
        if quality is None:
            config = get_config()
            try:
                quality = max(1, min(100, int(config.get("vision_jpeg_quality") or 72)))
            except (TypeError, ValueError):
                quality = 72
        return build_image_content_part(vision_image, quality=quality)
    except Exception:
        return None


def _messages_to_litellm_messages(messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """将内部消息结构转为 LiteLLM/OpenAI 兼容 messages。"""
    out: list[dict[str, Any]] = []
    for m in messages:
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if role == "assistant":
            out.append({"role": "assistant", "content": content})
            continue
        if role == "system":
            out.append({"role": "system", "content": content})
            continue
        if role == "user":
            parts: list[dict[str, Any]] = [{"type": "text", "text": content}]
            image_path = m.get("image_path")
            if image_path:
                img_part = _load_history_image_to_part(image_path)
                if img_part is not None:
                    parts.append(img_part)
            out.append({"role": "user", "content": parts if len(parts) > 1 else content})
    return out


async def chat_stream(
    current_user_input: str,
    *,
    mem0_lines: list[dict[str, Any]] | None = None,
    chat_history: list[dict[str, Any]] | None = None,
    vision_audio_text: str | None = None,
    vision_image: Any | None = None,
) -> AsyncIterator[str]:
    """接收当前回合上下文，组装后通过 llm-gateway 流式生成文本。"""
    config = get_config()
    api_key = get_gateway_api_key()
    if not api_key:
        logger.warning("LITELLM_API_KEY 未配置，将跳过真实调用")
        yield "[未配置 LITELLM_API_KEY]"
        return

    system_text = load_system_prompt()
    if not system_text:
        logger.warning("系统提示词为空：请配置 Langfuse 与 assets/prompts/langfuse_prompts.json")
        yield "[系统提示词未就绪：请检查 Langfuse 与 langfuse_prompts.json]"
        return

    messages = build_messages(
        mem0_lines=mem0_lines,
        chat_history=chat_history,
        vision_audio_text=vision_audio_text,
        vision_image_attached=(vision_image is not None),
        current_user_input=current_user_input,
    )

    llm_messages = _messages_to_litellm_messages(messages)
    if not llm_messages:
        yield ""
        return

    # 调试：将组装好的完整提示词打印到日志（config debug_log_prompt=true）
    if config.get("debug_log_prompt"):
        try:
            raw = json.dumps(messages, ensure_ascii=False, indent=2)
            max_len = 50000
            if len(raw) > max_len:
                raw = raw[:max_len] + f"\n... [已截断，共 {len(raw)} 字 ]"
            logger.info("[主脑] 完整组装提示词（发送前）:\n%s", raw)
        except Exception as e:
            logger.warning("[主脑] 打印组装提示词失败: %s", e)

    model_name = get_chat_model_name()
    if model_name.startswith("models/"):
        model_name = model_name.replace("models/", "", 1)

    max_output_tokens = 8192
    if config.get("gemini_max_output_tokens") is not None:
        try:
            max_output_tokens = max(256, min(65536, int(config.get("gemini_max_output_tokens"))))
        except (TypeError, ValueError):
            pass

    try:
        system_instruction = system_text

        if vision_image is not None and llm_messages and llm_messages[-1].get("role") == "user":
            tail = llm_messages[-1]
            image_part = _vision_image_to_part(vision_image)
            if image_part is not None:
                if isinstance(tail.get("content"), list):
                    tail["content"].append(image_part)
                else:
                    tail["content"] = [
                        {"type": "text", "text": str(tail.get("content", ""))},
                        image_part,
                    ]

        async for chunk in stream_chat(
            model_name=model_name,
            api_key=api_key,
            messages=llm_messages,
            system_instruction=system_instruction,
            max_output_tokens=max_output_tokens,
            trace_name="brain_chat_stream",
        ):
            yield chunk
    except RuntimeError as e:
        logger.error("llm-gateway 初始化失败: %s", e)
        yield "[请安装: pip install litellm langfuse]"
    except Exception as e:
        logger.exception("llm-gateway 流式调用异常: %s", e)
        err_msg = str(e).strip()
        if "API key" in err_msg or "401" in err_msg or "invalid_api_key" in err_msg.lower():
            yield (
                "[模型 API Key 无效] 请检查 .env 中的 LITELLM_API_KEY："
                " 在对应平台申请并启用模型服务，"
                f" 确保 Key 无多余空格、未过期。详细错误已写入 {get_log_path()}"
            )
        else:
            yield f"[生成错误: {err_msg[:200]}] 详见 {get_log_path()}"
