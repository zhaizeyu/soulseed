"""
对话服务 — 与 orchestrator 解耦，仅封装「单轮对话」逻辑，供 Web API 调用。
复用 config、memory、conscious、vision；历史与 CLI 共用唯一数据源（config chat_history_file）。
"""
import asyncio
from typing import AsyncIterator

from src.core.config_loader import get_config
from src.core.logger import get_logger
from src.brain import conscious
from src.brain import memory as memory_module
from src.brain.chat_history_store import load_history, append_turns
from src.senses import vision as vision_module

logger = get_logger(__name__)

_DEFAULT_MAX_ENTRIES = 20


class ConversationService:
    """
    单轮对话服务：不依赖 Orchestrator，内部调用 memory / conscious / vision。
    历史与 CLI 共用同一数据源（chat_history_store，即 config 中的 chat_history_file）。
    """

    def __init__(self) -> None:
        self._config = get_config()
        self._chat_history: list[dict[str, str]] = load_history()

    async def _get_vision_image(self):
        """本回合截图；未启用或失败返回 None。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, vision_module.get_screen_for_turn)

    async def run_one_turn(self, user_input: str) -> AsyncIterator[str]:
        """
        执行一轮：Mem0 检索 → 截屏（可选）→ 主脑流式生成；yield 文本片段。
        调用方在迭代结束后需调用 commit_turn(user_input, full_reply) 写入历史与记忆。
        """
        query = (user_input or "").strip()
        try:
            limit = max(1, int(self._config.get("mem0_search_limit", 5)))
            mem0_lines = await memory_module.search(query, top_k=limit)
        except Exception as e:
            logger.debug("Mem0 检索跳过: %s", e)
            mem0_lines = []

        vision_image = await self._get_vision_image()
        use_defaults = len(self._chat_history) == 0

        async for chunk in conscious.chat_stream(
            current_user_input=user_input,
            persona_name="vedal_main",
            user_info=None,
            mem0_lines=mem0_lines or None,
            chat_history=self._chat_history,
            vision_audio_text=None,
            vision_image=vision_image,
            use_defaults_for_missing=use_defaults,
        ):
            yield chunk

    def commit_turn(self, user_input: str, reply_text: str) -> None:
        """将本轮 user/assistant 追加到唯一历史存储（与 CLI 共用）。长期记忆由调用方在流结束后 await memory.add_background。"""
        user_input = (user_input or "").strip()
        reply_text = (reply_text or "").strip()
        new_turns: list[dict[str, str]] = []
        if user_input:
            self._chat_history.append({"role": "user", "content": user_input})
            new_turns.append({"role": "user", "content": user_input})
        self._chat_history.append({"role": "assistant", "content": reply_text})
        new_turns.append({"role": "assistant", "content": reply_text})
        append_turns(new_turns)

        max_entries = max(1, int(self._config.get("chat_history_max_entries", _DEFAULT_MAX_ENTRIES)))
        if len(self._chat_history) > max_entries:
            self._chat_history = self._chat_history[-max_entries:]
