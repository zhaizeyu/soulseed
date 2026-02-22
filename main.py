#!/usr/bin/env python3
"""
数字生命 MVP — 程序启动总入口
参见 docs/arch.md 架构设计。
"""
import asyncio

from src.core.logger import get_logger
from src.core.orchestrator import Orchestrator

logger = get_logger(__name__)


def main() -> None:
    """启动调度器主循环。"""
    logger.info("数字生命 MVP 启动中...")
    try:
        orch = Orchestrator()
        asyncio.run(orch.run())
    except KeyboardInterrupt:
        logger.info("用户中断，退出。")
    except Exception as e:
        logger.exception("运行异常: %s", e)
        raise


if __name__ == "__main__":
    main()
