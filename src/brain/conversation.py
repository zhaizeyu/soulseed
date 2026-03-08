"""
单轮对话流水线 — 仅做 Mem0 检索 → 视觉解析 → 主脑流式，不读写历史与记忆。
三端（CLI / Web / Telegram）统一调用本模块的 run_one_turn_stream，各自负责历史与记忆的存取。
"""
from typing import Any, AsyncIterator, Awaitable, Callable

from src.core.config_loader import get_config
from src.core.logger import get_logger
from src.brain import conscious
from src.brain import memory as memory_module
from src.brain.turn_input import UserTurnInput

logger = get_logger(__name__)

GetVisionImage = Callable[[], Awaitable[Any]]


async def run_one_turn_stream(
    turn_input: UserTurnInput,
    chat_history: list[dict[str, str]],
    *,
    persona_name: str = "vedal_main",
    user_info: str | None = None,
    mem0_user_id: str = "default",
    vision_image_override: Any = None,
    get_vision_image: GetVisionImage | None = None,
    vision_audio_text: str | None = None,
) -> AsyncIterator[str]:
    """
    单轮对话流水线：Mem0 检索 → 解析本回合视觉 → 主脑流式生成；yield 文本片段。
    不读写历史与记忆，由调用方在迭代结束后自行 append_turns + memory.add_background。
    """
    query = turn_input.effective_text()
    try:
        config = get_config()
        limit = max(1, int(config.get("mem0_search_limit", 5)))
        mem0_lines = await memory_module.search(query, top_k=limit, user_id=mem0_user_id)
    except Exception as e:
        logger.debug("Mem0 检索跳过: %s", e)
        mem0_lines = []

    if vision_image_override is not None:
        vision_image = vision_image_override
    elif get_vision_image is not None:
        vision_image = await get_vision_image()
    else:
        vision_image = turn_input.images[0] if turn_input.images else None

    use_defaults_for_missing = len(chat_history) == 0

    async for chunk in conscious.chat_stream(
        current_user_input=query,
        persona_name=persona_name,
        user_info=user_info,
        mem0_lines=mem0_lines or None,
        chat_history=chat_history,
        vision_audio_text=vision_audio_text,
        vision_image=vision_image,
        use_defaults_for_missing=use_defaults_for_missing,
    ):
        yield chunk
