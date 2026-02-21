"""
调度器 — 核心主循环，管理所有模块的异步协同与生命周期。
初始化感官与表达模块，协调数据流：hearing -> vision -> brain -> mouth/player/body；
支持用户插嘴时调用 player.interrupt() 清空播放队列。
"""
import asyncio
from typing import Any

from src.core.logger import get_logger

logger = get_logger(__name__)


class Orchestrator:
    """主游戏循环调度器。"""

    def __init__(self) -> None:
        # TODO: 初始化感官与表达模块实例
        self._running = False

    async def run(self) -> None:
        """启动 asyncio.gather 监听任务，协调数据流。"""
        self._running = True
        logger.info("调度器主循环已启动")
        # TODO: 启动 hearing / vision 监听，连接 brain -> mouth -> player -> body
        try:
            while self._running:
                await asyncio.sleep(1.0)
        except asyncio.CancelledError:
            self._running = False
            logger.info("调度器已停止")
