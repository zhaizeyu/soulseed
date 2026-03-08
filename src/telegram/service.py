"""
单轮对话服务：入参 chat_id + UserTurnInput，调用 memory + conscious，写本端历史与 Mem0。
与 Web/CLI 共用 brain 层，历史独立存于 telegram/history.py。
"""
from src.core.config_loader import get_config
from src.core.logger import get_logger
from src.brain import conscious
from src.brain import memory as memory_module
from src.brain.turn_input import UserTurnInput

from src.telegram import history as tg_history

logger = get_logger(__name__)


# 仅图片无文字时发给主脑的占位提示（历史与记忆里也存这句）
IMAGE_ONLY_PROMPT = "（用户发来一张图片，请根据图片内容回复。）"


async def run_turn(chat_id: int | str, turn_input: UserTurnInput) -> str:
    """
    执行一轮：Mem0 检索(user_id=tg_{chat_id}) → 主脑流式生成 → 写会话历史与长期记忆，返回完整回复。
    若既无文字也无图片（如语音转写失败），返回空字符串，不写历史与记忆。
    """
    user_text = turn_input.effective_text()
    has_image = bool(turn_input.images)
    if not user_text and not has_image:
        return ""
    if not user_text and has_image:
        user_text = IMAGE_ONLY_PROMPT

    session_id = f"tg_{chat_id}"
    chat_history = tg_history.get(chat_id)
    config = get_config()

    try:
        limit = max(1, int(config.get("mem0_search_limit", 5)))
        mem0_lines = await memory_module.search(user_text, top_k=limit, user_id=session_id)
    except Exception as e:
        logger.debug("Mem0 检索跳过: %s", e)
        mem0_lines = []

    vision_image = turn_input.images[0] if turn_input.images else None
    use_defaults = len(chat_history) == 0

    full_reply: str = ""
    async for chunk in conscious.chat_stream(
        current_user_input=user_text,
        persona_name="vedal_main",
        user_info=None,
        mem0_lines=mem0_lines or None,
        chat_history=chat_history,
        vision_audio_text=None,
        vision_image=vision_image,
        use_defaults_for_missing=use_defaults,
    ):
        full_reply += chunk

    full_reply = (full_reply or "").strip()
    tg_history.append(chat_id, user_text, full_reply)
    await memory_module.add_background(
        user_input=user_text,
        reply_text=full_reply,
        metadata=None,
        user_id=session_id,
    )
    return full_reply
