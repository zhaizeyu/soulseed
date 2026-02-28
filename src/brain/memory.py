"""
海马体 — 封装 Mem0，负责长期记忆的异步写入与检索。
使用 Google Gemini 作为 embedder 与 LLM，与主脑、语音转写统一为 Google 系列。
提供 search() 与 add_background() 异步方法。
"""
import asyncio
import os
from pathlib import Path
from typing import List, Optional

from src.core.config_loader import get_config
from src.core.logger import get_logger

logger = get_logger(__name__)

# 在首次使用前设置 MEM0 数据目录到项目内，避免写入 ~/.mem0
_project_root = Path(__file__).resolve().parents[2]
_mem0_dir = _project_root / "data" / "mem0"
os.environ.setdefault("MEM0_DIR", str(_mem0_dir))

_MEMORY: Optional[object] = None  # mem0.Memory 实例，未启用时为 None
_DEFAULT_USER_ID = "default"


def _get_memory():
    """懒加载 Mem0 Memory；缺 key 或缺库时返回 None。"""
    global _MEMORY
    if _MEMORY is not None:
        return _MEMORY
    cfg = get_config()
    api_key = (cfg.get("GEMINI_API_KEY") or "").strip()
    if not api_key:
        logger.warning("未配置 GEMINI_API_KEY，长期记忆 (Mem0) 未启用")
        return None
    try:
        from mem0 import Memory
    except ImportError as e:
        logger.warning("未安装 mem0ai，长期记忆未启用: %s", e)
        return None
    # 从 config.yaml 读取，无则用默认值
    embedder_model = cfg.get("mem0_embedder_model") or "gemini-embedding-001"
    llm_model = cfg.get("mem0_llm_model") or "gemini-2.0-flash"
    try:
        embedding_dims = int(cfg.get("mem0_embedding_dims") or 768)
    except (TypeError, ValueError):
        embedding_dims = 768
    try:
        llm_temperature = float(cfg.get("mem0_llm_temperature") or 0.2)
    except (TypeError, ValueError):
        llm_temperature = 0.2
    vector_path = cfg.get("mem0_vector_store_path") or str(_mem0_dir / "qdrant")
    config = {
        "embedder": {
            "provider": "gemini",
            "config": {
                "model": embedder_model,
                "api_key": api_key,
                "embedding_dims": embedding_dims,
            },
        },
        "llm": {
            "provider": "gemini",
            "config": {
                "model": llm_model,
                "temperature": llm_temperature,
                "api_key": api_key,
            },
        },
        "vector_store": {
            "provider": "qdrant",
            "config": {
                "path": vector_path,
                "embedding_model_dims": embedding_dims,
            },
        },
    }
    try:
        _MEMORY = Memory.from_config(config)
        logger.info("Mem0 长期记忆已启用（Gemini embedder + LLM）")
        return _MEMORY
    except Exception as e:
        logger.warning("Mem0 初始化失败，长期记忆未启用: %s", e)
        return None


async def search(query: str, top_k: int = 5) -> List[str]:
    """根据 query 检索相关长期记忆片段。未启用 Mem0 或 query 为空时返回空列表。"""
    memory = _get_memory()
    if memory is None or not (query or "").strip():
        return []
    limit = max(1, min(top_k, 100))
    loop = asyncio.get_event_loop()

    def _search() -> List[str]:
        result = memory.search(
            query,
            user_id=_DEFAULT_USER_ID,
            limit=limit,
        )
        items = result.get("results") or []
        return [str(item.get("memory", "")).strip() for item in items if item.get("memory")]

    try:
        return await loop.run_in_executor(None, _search)
    except Exception as e:
        logger.exception("Mem0 search 异常: %s", e)
        return []


async def add_background(user_input: str | None, reply_text: str) -> None:
    """对话结束后写入长期记忆。未启用 Mem0 时静默跳过。
    user_input: 本轮用户输入（mem0_infer=true 时与 reply 一起送 LLM 抽事实）
    reply_text: 本轮助手回复。
    """
    memory = _get_memory()
    if memory is None or not (reply_text or "").strip():
        return
    cfg = get_config()
    infer = cfg.get("mem0_infer", True)
    if isinstance(infer, str):
        infer = infer not in ("false", "0", "no", "off")
    loop = asyncio.get_event_loop()

    def _add() -> None:
        if infer and (user_input or "").strip():
            # 先尝试只抽取事实；若 LLM 返回非法 JSON（Mem0 会打 Invalid JSON response），降级为存原文
            messages = [
                {"role": "user", "content": (user_input or "").strip()},
                {"role": "assistant", "content": reply_text.strip()},
            ]
            try:
                memory.add(messages, user_id=_DEFAULT_USER_ID, infer=True)
            except Exception as e:
                logger.debug("事实抽取失败，改为存原文: %s", e)
                memory.add(
                    [{"role": "assistant", "content": reply_text.strip()}],
                    user_id=_DEFAULT_USER_ID,
                    infer=False,
                )
        else:
            memory.add(
                [{"role": "assistant", "content": reply_text.strip()}],
                user_id=_DEFAULT_USER_ID,
                infer=False,
            )

    def _run() -> None:
        try:
            _add()
        except Exception as e:
            logger.exception("Mem0 add_background 异常: %s", e)

    # 等待写入完成再返回，避免 Ctrl+C 退出时写入未完成导致记忆丢失
    await loop.run_in_executor(None, _run)
