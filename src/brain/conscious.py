"""
主脑 — 封装 Gemini API（google-genai），处理多模态上下文与对话会话管理。
按 prompt_assembler 的消息顺序逐条喂给大模型，不合并 system；Gemini 仅支持 user/model，
故将 system 转为带 [System] 标记的 user + 空 model 以保持顺序。
"""
import io
import json
from typing import Any, AsyncIterator

from src.core.config_loader import get_config
from src.core.logger import get_logger, get_log_path
from src.brain.prompt_assembler import build_messages

logger = get_logger(__name__)

# Gemini 仅支持 user/model 交替，system 用此前缀标识且后接空 model 占位
_SYSTEM_PREFIX = "[System]\n"


def _messages_to_genai_contents(messages: list[dict[str, Any]]) -> tuple[list[Any], str]:
    """
    将 messages 转为 google.genai types.Content 列表与当前 user 文本。
    返回 (history_contents, current_user_text)。
    """
    from google.genai import types

    last_user_idx: int | None = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break

    contents: list[Any] = []
    current_user_text = ""
    for i, m in enumerate(messages):
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if role == "user" and i == last_user_idx:
            current_user_text = content
            continue
        if role == "system":
            contents.append(
                types.Content(
                    role="user",
                    parts=[types.Part.from_text(text=_SYSTEM_PREFIX + content)],
                )
            )
            contents.append(types.Content(role="model", parts=[types.Part.from_text(text="")]))
        elif role == "user":
            contents.append(
                types.Content(role="user", parts=[types.Part.from_text(text=content)])
            )
        elif role == "assistant":
            contents.append(
                types.Content(role="model", parts=[types.Part.from_text(text=content)])
            )

    return contents, current_user_text


def _vision_image_to_part(vision_image: Any) -> Any:
    """将 PIL.Image 转为 google.genai types.Part（JPEG bytes）。"""
    from google.genai import types

    if vision_image is None:
        return None
    try:
        from PIL import Image
        if not isinstance(vision_image, Image.Image):
            return None
        buf = io.BytesIO()
        vision_image.save(buf, format="JPEG", quality=85)
        return types.Part.from_bytes(data=buf.getvalue(), mime_type="image/jpeg")
    except Exception:
        return None


async def chat_stream(
    current_user_input: str,
    *,
    persona_name: str = "vedal_main",
    user_info: str | None = None,
    mem0_lines: list[str] | None = None,
    chat_history: list[dict[str, str]] | None = None,
    vision_audio_text: str | None = None,
    vision_image: Any | None = None,
    use_defaults_for_missing: bool = False,
) -> AsyncIterator[str]:
    """
    接收当前用户输入与可选上下文，组装 prompt 后调用 Gemini（google-genai）流式生成，yield 文本片段。
    调用方负责维护 chat_history（每轮结束后追加 user 与 assistant 的 content）。
    """
    config = get_config()
    api_key = (config.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        logger.warning("GEMINI_API_KEY 未配置，将跳过真实调用")
        yield "[未配置 GEMINI_API_KEY]"
        return

    messages = build_messages(
        persona_name=persona_name,
        user_info=user_info,
        mem0_lines=mem0_lines,
        chat_history=chat_history,
        vision_audio_text=vision_audio_text,
        vision_image_attached=(vision_image is not None),
        current_user_input=current_user_input,
        use_defaults_for_missing=use_defaults_for_missing,
    )

    try:
        history_contents, current_user_text = _messages_to_genai_contents(messages)
    except ImportError as e:
        logger.error("未安装 google-genai: %s", e)
        yield "[请安装: pip install google-genai]"
        return

    if not current_user_text and not history_contents:
        yield ""
        return

    from google.genai import types

    image_part = _vision_image_to_part(vision_image)
    user_parts: list[Any] = [types.Part.from_text(text=current_user_text or "")]
    if image_part is not None:
        user_parts.append(image_part)
    current_content = types.Content(role="user", parts=user_parts)
    all_contents = history_contents + [current_content]

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

    model_name = (config.get("gemini_model") or config.get("GEMINI_MODEL") or "gemini-2.0-flash").strip()
    if model_name.startswith("models/"):
        model_name = model_name.replace("models/", "", 1)

    max_output_tokens = 8192
    if config.get("gemini_max_output_tokens") is not None:
        try:
            max_output_tokens = max(256, min(65536, int(config.get("gemini_max_output_tokens"))))
        except (TypeError, ValueError):
            pass

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        async for chunk in await client.aio.models.generate_content_stream(
            model=model_name,
            contents=all_contents,
            config=types.GenerateContentConfig(max_output_tokens=max_output_tokens),
        ):
            try:
                if getattr(chunk, "text", None):
                    yield chunk.text
            except (ValueError, AttributeError):
                logger.warning(
                    "[主脑] 流式返回无有效 Part，输出已截断（可能原因：安全/引用过滤，或回复过长触及 gemini_max_output_tokens 上限）"
                )
    except ImportError as e:
        logger.error("未安装 google-genai: %s", e)
        yield "[请安装: pip install google-genai]"
    except Exception as e:
        logger.exception("Gemini 流式调用异常: %s", e)
        err_msg = str(e).strip()
        if "API key not valid" in err_msg or "API_KEY_INVALID" in err_msg or "401" in err_msg:
            yield (
                "[Gemini API Key 无效] 请检查 .env 中的 GEMINI_API_KEY："
                " 在 https://aistudio.google.com/apikey 申请并启用 Generative Language API，"
                f" 确保 Key 无多余空格、未过期。详细错误已写入 {get_log_path()}"
            )
        else:
            yield f"[生成错误: {err_msg[:200]}] 详见 {get_log_path()}"
