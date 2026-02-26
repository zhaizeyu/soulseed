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
from src.brain.chat_history_store import load_history, append_turns
from src.brain import memory as memory_module
from src.senses import vision as vision_module

logger = get_logger(__name__)


class Orchestrator:
    """主游戏循环调度器。"""

    def __init__(self) -> None:
        self._running = False
        self._config = get_config()
        # 历史对话（仅 user/assistant），从 JSON 加载最近 N 条，每轮追加后写回
        self._chat_history: list[dict[str, str]] = load_history()
        # Mem0 检索结果（占位，后续接 memory.search）
        self._mem0_lines: list[str] = []

    async def _get_user_input(self) -> str:
        """模拟用户输入：在 executor 中读 stdin，不阻塞事件循环。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, lambda: input("你: ").strip())

    async def _get_vision_audio_text(self) -> str:
        """当前环境感知（耳朵）。眼睛已通过 vision_image 单独传入主脑。"""
        return ""

    async def _get_vision_image(self):
        """本回合屏幕截图，供主脑多模态；未启用或失败时返回 None。"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(None, vision_module.get_screen_for_turn)

    async def _run_one_turn(self, user_input: str) -> None:
        """执行一轮：主脑流式生成，打印并写入历史。用户直接回车（空输入）时按「继续说话」处理。"""
        # 每轮开始前：从 Mem0 检索相关长期记忆
        try:
            limit = max(1, int(self._config.get("mem0_search_limit", 5)))
            self._mem0_lines = await memory_module.search(user_input.strip(), top_k=limit)
        except Exception as e:
            logger.debug("Mem0 检索跳过: %s", e)
            self._mem0_lines = []
        vision_audio = await self._get_vision_audio_text()
        vision_image = await self._get_vision_image()
        full_reply: list[str] = []
        try:
            async for chunk in conscious.chat_stream(
                current_user_input=user_input,
                persona_name="vedal_main",
                user_info=None,
                mem0_lines=self._mem0_lines or None,
                chat_history=self._chat_history,
                vision_audio_text=vision_audio or None,
                vision_image=vision_image,
                use_defaults_for_missing=(len(self._chat_history) == 0),
            ):
                full_reply.append(chunk)
                print(chunk, end="", flush=True)
            print()
        except Exception as e:
            logger.exception("主脑本轮异常: %s", e)
            full_reply.append(f"[错误: {e}]")
        reply_text = "".join(full_reply).strip()
        new_turns: list[dict[str, str]] = []
        if (user_input or "").strip():
            self._chat_history.append({"role": "user", "content": user_input.strip()})
            new_turns.append({"role": "user", "content": user_input.strip()})
        self._chat_history.append({"role": "assistant", "content": reply_text})
        new_turns.append({"role": "assistant", "content": reply_text})
        append_turns(new_turns)
        # 保持内存中仅最近 N 条（与 config chat_history_max_entries 一致）
        try:
            max_entries = max(1, int(self._config.get("chat_history_max_entries", 20)))
        except (TypeError, ValueError):
            max_entries = 20
        if len(self._chat_history) > max_entries:
            self._chat_history = self._chat_history[-max_entries:]
        # 每轮结束后：写入长期记忆并等待完成，避免 Ctrl+C 退出时未落盘
        if reply_text:
            await memory_module.add_background(user_input.strip() if user_input else None, reply_text)

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
