"""
调度器 — 核心主循环，管理所有模块的异步协同与生命周期。
第一步：模拟用户输入 → 主脑（prompt 组装 + Gemini 流式）→ 控制台输出；维护 chat_history。
后续：接入 hearing / vision / mouth / player / body。
"""
import asyncio
from typing import Any

from src.core.config_loader import get_config
from src.core.logger import get_logger
from src.brain import conscious

logger = get_logger(__name__)


class Orchestrator:
    """主游戏循环调度器。"""

    def __init__(self) -> None:
        self._running = False
        self._config = get_config()
        # 历史对话（仅 user/assistant 轮次），供 prompt 组装与主脑使用
        self._chat_history: list[dict[str, str]] = []
        # Mem0 检索结果（占位，后续接 memory.search）
        self._mem0_lines: list[str] = []

    async def _get_user_input(self) -> str:
        """模拟用户输入：在 executor 中读 stdin，不阻塞事件循环。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input("你: ").strip())

    async def _get_vision_audio_text(self) -> str:
        """当前环境感知（眼睛与耳朵）。第一步用占位或空，后续接 vision + hearing。"""
        return ""

    async def _run_one_turn(self, user_input: str) -> None:
        """执行一轮：主脑流式生成，打印并写入历史。"""
        if not user_input:
            return
        vision_audio = await self._get_vision_audio_text()
        full_reply: list[str] = []
        try:
            async for chunk in conscious.chat_stream(
                current_user_input=user_input,
                persona_name="vedal_main",
                user_info=None,
                mem0_lines=self._mem0_lines or None,
                chat_history=self._chat_history,
                vision_audio_text=vision_audio or None,
                use_defaults_for_missing=(len(self._chat_history) == 0),
            ):
                full_reply.append(chunk)
                print(chunk, end="", flush=True)
            print()
        except Exception as e:
            logger.exception("主脑本轮异常: %s", e)
            full_reply.append(f"[错误: {e}]")
        reply_text = "".join(full_reply).strip()
        if (user_input or "").strip():
            self._chat_history.append({"role": "user", "content": user_input.strip()})
        self._chat_history.append({"role": "assistant", "content": reply_text})
        # 可选：异步写入 Mem0（不阻塞），后续接 memory.add_background

    async def run(self) -> None:
        """主循环：模拟输入 → 主脑流式 → 打印，直到用户输入 exit/quit。"""
        self._running = True
        logger.info("调度器已启动（第一步：模拟输入 + Gemini 流式）")
        logger.info("输入内容后回车发送；直接回车让助手继续说话；输入 exit 或 quit 退出")
        try:
            while self._running:
                try:
                    user_input = await self._get_user_input()
                except (EOFError, KeyboardInterrupt):
                    break
                if user_input is None:
                    continue
                if user_input.strip().lower() in ("exit", "quit", "退出"):
                    logger.info("用户退出")
                    break
                await self._run_one_turn(user_input)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            logger.info("调度器已停止")
