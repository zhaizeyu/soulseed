"""
对话服务 — 与 orchestrator 解耦，仅封装「单轮对话」逻辑，供 Web API 调用。
复用 config、memory、conscious、vision；历史与 CLI 共用唯一数据源（config chat_history_file）。
支持心跳触发：外部传入 vision_image_override 与主动说话提示词即可跑「主动回合」。
"""
import asyncio
from typing import Any, AsyncIterator

from src.core.config_loader import get_config
from src.core.logger import get_logger
from src.brain.conversation import run_one_turn_stream
from src.brain import memory as memory_module
from src.brain.turn_input import UserTurnInput
from src.brain.chat_history_store import load_history, append_turns
from src.senses import vision as vision_module

logger = get_logger(__name__)

# 心跳触发时注入的用户侧提示，与 CLI 一致
HEARTBEAT_PROACTIVE_PROMPT = "（系统：画面发生了你感兴趣的变化，请根据当前画面主动说说你的看法。）"

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

    async def run_one_turn(
        self,
        user_input: str,
        vision_image_override: Any = None,
    ) -> AsyncIterator[str]:
        """
        执行一轮：Mem0 检索 → 截屏（或 vision_image_override）→ 主脑流式；yield 文本片段。
        入参在内部封装为 UserTurnInput，便于后续扩展图片/语音等不改签名。
        调用方在迭代结束后需调用 commit_turn(user_input, full_reply) 写入历史与记忆。
        """
        turn_input = UserTurnInput(text=user_input or "", images=None)
        async for chunk in run_one_turn_stream(
            turn_input,
            self._chat_history,
            get_vision_image=self._get_vision_image,
            vision_image_override=vision_image_override,
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
