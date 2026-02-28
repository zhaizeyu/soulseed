"""
调度器 — 核心主循环，管理所有模块的异步协同与生命周期。
第一步：模拟用户输入 → 主脑（prompt 组装 + Gemini 流式）→ 控制台输出；维护 chat_history。
眼睛心跳：每 N 秒截图与上一张对比，有显著变化则触发主动说话（队列注入一条「系统：画面有变化…」回合）。
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

# 心跳触发时注入的用户侧提示，让主脑根据当前画面主动说话
HEARTBEAT_PROACTIVE_PROMPT = "（系统：画面发生了你感兴趣的变化，请根据当前画面主动说说你的看法。）"


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

    async def _run_one_turn(
        self,
        user_input: str,
        vision_image_override: Any = None,
    ) -> None:
        """执行一轮：主脑流式生成，打印并写入历史。vision_image_override 非空时替代本回合截图（用于心跳触发）。"""
        # 每轮开始前：从 Mem0 检索相关长期记忆
        try:
            limit = max(1, int(self._config.get("mem0_search_limit", 5)))
            self._mem0_lines = await memory_module.search(user_input.strip(), top_k=limit)
        except Exception as e:
            logger.debug("Mem0 检索跳过: %s", e)
            self._mem0_lines = []
        vision_audio = await self._get_vision_audio_text()
        vision_image = vision_image_override if vision_image_override is not None else await self._get_vision_image()
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

    async def _heartbeat_loop(self, queue: asyncio.Queue) -> None:
        """后台任务：每 N 秒执行一次心跳检测，有变化则向队列注入触发。"""
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                interval = max(1, int(self._config.get("vision_heartbeat_interval_sec", 30)))
            except (TypeError, ValueError):
                interval = 30
            await asyncio.sleep(interval)
            if not self._running:
                break
            if not self._config.get("vision_heartbeat_enabled", False):
                logger.debug("心跳检测已关闭 (vision_heartbeat_enabled=false)，跳过")
                continue
            try:
                triggered, image = await loop.run_in_executor(None, vision_module.check_heartbeat)
                if triggered and image is not None:
                    logger.info("[调度器] 心跳触发主动说话，已放入队列")
                    await queue.put(("heartbeat", HEARTBEAT_PROACTIVE_PROMPT, image))
            except Exception as e:
                logger.warning("心跳检测异常: %s", e, exc_info=True)

    async def _user_input_loop(self, queue: asyncio.Queue) -> None:
        """后台任务：阻塞读 stdin，每行放入队列。"""
        loop = asyncio.get_event_loop()
        while self._running:
            try:
                line = await loop.run_in_executor(None, lambda: input("你: ").strip())
            except (EOFError, KeyboardInterrupt):
                await queue.put(("user", None, None))  # 用 None 表示退出
                break
            await queue.put(("user", line or "", None))

    async def run(self) -> None:
        """主循环：等待用户输入或心跳触发 → 主脑流式 → 打印，直到用户输入 exit/quit。"""
        self._running = True
        logger.info("调度器已启动（模拟输入 + Gemini 流式 + 眼睛心跳检测）")
        logger.info("输入内容后回车发送；直接回车让助手继续说话；输入 exit 或 quit 退出")
        hb_enabled = self._config.get("vision_heartbeat_enabled", False)
        hb_interval = self._config.get("vision_heartbeat_interval_sec", 30)
        if hb_enabled:
            logger.info("眼睛心跳: 已开启，每 %s 秒检测画面变化，有变化则触发主动说话（首次对比约在 %s 秒后）", hb_interval, int(hb_interval) * 2)
        else:
            logger.info("眼睛心跳: 未开启 (vision_heartbeat_enabled=false)")
        queue: asyncio.Queue = asyncio.Queue()
        user_task = asyncio.create_task(self._user_input_loop(queue))
        heartbeat_task = asyncio.create_task(self._heartbeat_loop(queue))
        try:
            while self._running:
                kind, user_input, vision_image = await queue.get()
                if kind == "user":
                    if user_input is None:
                        break
                    if user_input.strip().lower() in ("exit", "quit", "退出"):
                        logger.info("用户退出")
                        break
                    await self._run_one_turn(user_input)
                elif kind == "heartbeat":
                    await self._run_one_turn(user_input, vision_image_override=vision_image)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False
            user_task.cancel()
            heartbeat_task.cancel()
            try:
                await user_task
            except asyncio.CancelledError:
                pass
            try:
                await heartbeat_task
            except asyncio.CancelledError:
                pass
            logger.info("调度器已停止")
