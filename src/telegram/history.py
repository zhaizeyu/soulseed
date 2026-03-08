"""
按 chat_id 的会话历史存储，与核心 chat_history_store 解耦，逻辑一致：全量写入，读取时只返回最近 N 条作上下文。
格式与主脑一致：[{ "role": "user"|"assistant", "content": "..." }, ...]
存储路径：data/telegram/chats/{chat_id}.json。
"""
import json
from pathlib import Path
from typing import Any

from src.core.config_loader import get_config
from src.core.logger import get_logger

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _get_chat_history_dir() -> Path:
    cfg = get_config()
    raw = (cfg.get("telegram_chat_history_dir") or "data/telegram/chats").strip()
    p = Path(raw)
    if p.is_absolute():
        return p
    return _PROJECT_ROOT / raw


def _get_max_entries() -> int:
    cfg = get_config()
    n = cfg.get("telegram_max_history_entries") or cfg.get("chat_history_max_entries")
    if n is None:
        return 20
    try:
        return max(1, int(n))
    except (TypeError, ValueError):
        return 20


def _safe_filename(chat_id: int | str) -> str:
    """将 chat_id 转为安全文件名（仅数字与负号保留，负号改为 m）。"""
    s = str(chat_id).strip()
    return "".join(c if c.isalnum() or c == "-" else "_" for c in s).replace("-", "m") or "0"


def get(chat_id: int | str) -> list[dict[str, str]]:
    """
    加载该会话的历史，只返回最近 max_entries 条供主脑作上下文；文件内为全量历史。
    文件不存在或为空时返回 []。
    """
    base = _get_chat_history_dir()
    path = base / f"{_safe_filename(chat_id)}.json"
    max_entries = _get_max_entries()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("加载 Telegram 历史失败 %s: %s", path, e)
        return []
    if not isinstance(data, list):
        return []
    items = [
        x
        for x in data
        if isinstance(x, dict)
        and x.get("role") in ("user", "assistant")
        and (x.get("content") is not None)
    ]
    return items[-max_entries:] if len(items) > max_entries else items


def append(chat_id: int | str, user_content: str, assistant_content: str) -> None:
    """追加一轮 user + assistant 到该会话历史，全量写入文件（不截断）；发给主脑的条数由 get() 按 max_entries 控制。"""
    user_content = (user_content or "").strip()
    assistant_content = (assistant_content or "").strip()
    base = _get_chat_history_dir()
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{_safe_filename(chat_id)}.json"
    existing: list[dict[str, Any]] = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    if not isinstance(existing, list):
        existing = []
    if user_content:
        existing.append({"role": "user", "content": user_content})
    existing.append({"role": "assistant", "content": assistant_content})
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning("写入 Telegram 历史失败 %s: %s", path, e)


def clear(chat_id: int | str) -> None:
    """清空该会话的上下文窗口历史（不删 Mem0 记忆）。"""
    base = _get_chat_history_dir()
    path = base / f"{_safe_filename(chat_id)}.json"
    if path.exists():
        try:
            path.unlink()
        except OSError as e:
            logger.warning("清空 Telegram 历史失败 %s: %s", path, e)
