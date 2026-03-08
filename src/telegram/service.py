"""
单轮对话服务：入参 chat_id + UserTurnInput，调用 brain 流水线，写本端历史与 Mem0。
与 Web/CLI 共用 brain 层，历史独立存于 telegram/history.py。
"""
from src.core.logger import get_logger
from src.brain.conversation import run_one_turn_stream
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
    turn_for_brain = UserTurnInput(text=user_text, images=turn_input.images)

    full_reply: str = ""
    async for chunk in run_one_turn_stream(
        turn_for_brain,
        chat_history,
        mem0_user_id=session_id,
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
