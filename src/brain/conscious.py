"""
主脑 — 封装 Gemini API，处理多模态上下文与对话会话管理。
按 prompt_assembler 的消息顺序逐条喂给大模型，不合并 system；Gemini 仅支持 user/model，
故将 system 转为带 [System] 标记的 user + 空 model 以保持顺序。
"""
import warnings
from typing import Any, AsyncIterator

from src.core.config_loader import get_config
from src.core.logger import get_logger, get_log_path
from src.brain.prompt_assembler import build_messages

logger = get_logger(__name__)

# Gemini 仅支持 user/model 交替，system 用此前缀标识且后接空 model 占位
_SYSTEM_PREFIX = "[System]\n"


def _messages_to_gemini_contents(messages: list[dict[str, Any]]) -> tuple[list[Any], str]:
    """
    按原始顺序将每条消息转为 Gemini Content，不合并。
    返回 (history_contents, current_user_content)。
    - system -> user("[System]\\n" + content) + model("") 以保持顺序
    - user -> user(content)；最后一条 user 作为本次 send_message 内容，其余按序进 history
    - assistant -> model(content)
    """
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=FutureWarning)
        try:
            from google.generativeai import protos
        except ImportError:
            raise RuntimeError("请安装 google-generativeai: pip install google-generativeai")

    last_user_idx: int | None = None
    for i in range(len(messages) - 1, -1, -1):
        if messages[i].get("role") == "user":
            last_user_idx = i
            break

    contents: list[Any] = []
    current_user_content = ""
    for i, m in enumerate(messages):
        role = m.get("role", "")
        content = (m.get("content") or "").strip()
        if role == "user" and i == last_user_idx:
            current_user_content = content
            continue
        if role == "system":
            contents.append(protos.Content(role="user", parts=[protos.Part(text=_SYSTEM_PREFIX + content)]))
            contents.append(protos.Content(role="model", parts=[protos.Part(text="")]))
        elif role == "user":
            contents.append(protos.Content(role="user", parts=[protos.Part(text=content)]))
        elif role == "assistant":
            contents.append(protos.Content(role="model", parts=[protos.Part(text=content)]))

    return contents, current_user_content


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
    接收当前用户输入与可选上下文，组装 prompt 后调用 Gemini 流式生成，yield 文本片段。
    调用方负责维护 chat_history（每轮结束后追加 user 与 assistant 的 content）。
    """
    config = get_config()
    api_key = config.get("GEMINI_API_KEY") or ""
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

    history_contents, current_user_content = _messages_to_gemini_contents(messages)
    if not history_contents and not current_user_content:
        yield ""
        return

    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", category=FutureWarning)
            import google.generativeai as genai
            genai.configure(api_key=api_key)
    except ImportError:
        logger.error("未安装 google-generativeai")
        yield "[请安装: pip install google-generativeai]"
        return

    model_name = config.get("gemini_model") or config.get("GEMINI_MODEL") or "gemini-2.0-flash"
    if not model_name.startswith("models/"):
        model_name = f"models/{model_name}"

    try:
        # 不设 system_instruction，全部按顺序放在 history 中
        model = genai.GenerativeModel(model_name=model_name)
        chat = model.start_chat(history=history_contents)
        # 本回合发送内容：仅组装好的用户文字 + 可选截图（§7 保证必有 user，不会为空）
        user_message: Any = current_user_content
        if vision_image is not None:
            user_message = [user_message, vision_image]
        response = chat.send_message(user_message, stream=True)
        for chunk in response:
            if chunk.text:
                yield chunk.text
    except Exception as e:
        logger.exception("Gemini 流式调用异常: %s", e)
        err_msg = str(e).strip()
        if "API key not valid" in err_msg or "API_KEY_INVALID" in err_msg:
            yield (
                "[Gemini API Key 无效] 请检查 .env 中的 GEMINI_API_KEY："
                " 在 https://aistudio.google.com/apikey 申请并启用 Generative Language API，"
                f" 确保 Key 无多余空格、未过期。详细错误已写入 {get_log_path()}"
            )
        else:
            yield f"[生成错误: {err_msg[:200]}] 详见 {get_log_path()}"
