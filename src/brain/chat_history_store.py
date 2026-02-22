"""
历史对话存取 — 所有对话持久化到 JSON 文件，每次只加载最新的 N 条（默认 20）。
格式：[{ "role": "user"|"assistant", "content": "..." }, ...]
"""
import json
from pathlib import Path
from typing import Any

from src.core.config_loader import get_config
from src.core.logger import get_logger

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def _get_history_path() -> Path:
    """从 config 取历史文件路径，相对项目根。"""
    cfg = get_config()
    raw = (cfg.get("chat_history_file") or "data/chat_history.json").strip()
    p = Path(raw)
    if p.is_absolute():
        return p
    return _PROJECT_ROOT / raw


def _get_max_entries() -> int:
    """从 config 取最大条数。"""
    cfg = get_config()
    n = cfg.get("chat_history_max_entries")
    if n is None:
        return 20
    try:
        return max(1, int(n))
    except (TypeError, ValueError):
        return 20


def load_history() -> list[dict[str, str]]:
    """
    从 JSON 文件加载历史对话，只返回最新的 max_entries 条。
    文件不存在或为空时返回 []。
    """
    path = _get_history_path()
    max_entries = _get_max_entries()
    if not path.exists():
        return []
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        logger.warning("加载历史对话失败 %s: %s", path, e)
        return []
    if not isinstance(data, list):
        return []
    items = [x for x in data if isinstance(x, dict) and x.get("role") in ("user", "assistant") and (x.get("content") is not None)]
    return items[-max_entries:] if len(items) > max_entries else items


def append_turns(turns: list[dict[str, str]]) -> None:
    """
    将本轮对话（若干条 user/assistant）追加到 JSON 文件。
    先读全量，追加后写回，保证文件内为完整历史。
    """
    if not turns:
        return
    path = _get_history_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    existing: list[dict[str, Any]] = []
    if path.exists():
        try:
            with open(path, "r", encoding="utf-8") as f:
                existing = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass
    if not isinstance(existing, list):
        existing = []
    valid = [{"role": t["role"], "content": t.get("content", "")} for t in turns if isinstance(t, dict) and t.get("role") in ("user", "assistant")]
    existing.extend(valid)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning("写入历史对话失败 %s: %s", path, e)
