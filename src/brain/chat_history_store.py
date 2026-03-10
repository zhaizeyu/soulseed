"""
历史对话存取 — 统一存储层，与客户端解耦。CLI/Web 不传 session_id；Telegram 传 session_id="tg_{chat_id}"。
格式：[{ "role", "content", "timestamp", "image_path"? }, ...]。带图回合落盘到 data/vision/history/ 并以 image_path 引用。
"""
import json
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config_loader import get_config
from src.core.logger import get_logger

logger = get_logger(__name__)

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_HISTORY_IMAGES_DIR = _PROJECT_ROOT / "data" / "vision" / "history"


def _safe_session_filename(session_id: str) -> str:
    """session_id 转为安全文件名（用于 JSON 路径）。"""
    s = (session_id or "").strip()
    return "".join(c if c.isalnum() or c in "-_" else "_" for c in s).strip("_") or "default"


def _get_history_path(session_id: str | None = None) -> Path:
    """根据 session_id 返回历史 JSON 路径。None = 默认（CLI/Web）；tg_* = Telegram 会话。"""
    cfg = get_config()
    if session_id is None or session_id == "":
        raw = (cfg.get("chat_history_file") or "data/chat_history.json").strip()
        p = Path(raw)
        if p.is_absolute():
            return p
        return _PROJECT_ROOT / raw
    if session_id.startswith("tg_"):
        raw = (cfg.get("telegram_chat_history_dir") or "data/telegram/chats").strip()
        base = Path(raw) if Path(raw).is_absolute() else _PROJECT_ROOT / raw
        return base / f"{_safe_session_filename(session_id[3:])}.json"
    # 其他 session 可扩展，如 web_session_id
    raw = (cfg.get("chat_history_file") or "data/chat_history.json").strip()
    base = Path(raw).parent if Path(raw).is_absolute() else _PROJECT_ROOT / Path(raw).parent
    return base / f"session_{_safe_session_filename(session_id)}.json"


def _get_max_entries(session_id: str | None = None) -> int:
    """根据 session_id 返回最大条数。"""
    cfg = get_config()
    if session_id is not None and session_id.startswith("tg_"):
        n = cfg.get("telegram_max_history_entries") or cfg.get("chat_history_max_entries")
    else:
        n = cfg.get("chat_history_max_entries")
    if n is None:
        return 20
    try:
        return max(1, int(n))
    except (TypeError, ValueError):
        return 20


def _save_history_image(image: Any, session_id: str | None = None) -> str | None:
    """将 PIL.Image 保存到 data/vision/history，返回相对项目根的路径。session_id 用于文件名前缀避免冲突。"""
    if image is None:
        return None
    try:
        from PIL import Image
        if not isinstance(image, Image.Image):
            return None
    except ImportError:
        return None
    _HISTORY_IMAGES_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    prefix = _safe_session_filename(session_id or "default")
    path = _HISTORY_IMAGES_DIR / f"history_{prefix}_{stamp}.jpg"
    try:
        cfg = get_config()
        q = 72
        try:
            q = max(1, min(100, int(cfg.get("vision_jpeg_quality") or 72)))
        except (TypeError, ValueError):
            pass
        image.save(path, "JPEG", quality=q, optimize=True)
        return str(path.relative_to(_PROJECT_ROOT))
    except Exception as e:
        logger.warning("保存历史图片失败 %s: %s", path, e)
        return None


def load_history(session_id: str | None = None) -> list[dict[str, Any]]:
    """
    从 JSON 加载历史对话，返回最新 max_entries 条。
    session_id=None 为默认会话（CLI/Web）；session_id="tg_{chat_id}" 为 Telegram 会话。
    每项含 role, content, timestamp（可选）, image_path（可选）。旧数据保留兼容。
    """
    path = _get_history_path(session_id)
    max_entries = _get_max_entries(session_id)
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
    items = []
    for x in data:
        if not isinstance(x, dict) or x.get("role") not in ("user", "assistant"):
            continue
        content = x.get("content")
        if content is None:
            continue
        items.append({
            "role": x["role"],
            "content": content,
            "timestamp": x.get("timestamp", ""),
            "image_path": x.get("image_path"),
        })
    return items[-max_entries:] if len(items) > max_entries else items


def append_turns(turns: list[dict[str, Any]], session_id: str | None = None) -> None:
    """
    将本轮对话追加到 JSON。每项可为 { role, content, image? }。
    session_id=None 为默认会话（CLI/Web）；session_id="tg_{chat_id}" 为 Telegram 会话。
    若 user 项带 image（PIL.Image），会保存到 data/vision/history 并写入 image_path；每条自动带 timestamp。
    """
    if not turns:
        return
    path = _get_history_path(session_id)
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

    now_iso = datetime.now().isoformat(timespec="seconds")
    for t in turns:
        if not isinstance(t, dict) or t.get("role") not in ("user", "assistant"):
            continue
        role = t["role"]
        content = t.get("content", "")
        image = t.get("image")
        image_path = None
        if role == "user" and image is not None:
            image_path = _save_history_image(image, session_id)
        record: dict[str, Any] = {
            "role": role,
            "content": content,
            "timestamp": now_iso,
        }
        if image_path:
            record["image_path"] = image_path
        existing.append(record)
    try:
        with open(path, "w", encoding="utf-8") as f:
            json.dump(existing, f, ensure_ascii=False, indent=2)
    except OSError as e:
        logger.warning("写入历史对话失败 %s: %s", path, e)


def clear_history(session_id: str | None = None) -> None:
    """清空指定会话的历史文件（不删 Mem0）。session_id=None 时清默认会话；tg_* 时清对应 Telegram 会话。"""
    path = _get_history_path(session_id)
    if path.exists():
        try:
            path.unlink()
            logger.info("已清空历史: %s", path)
        except OSError as e:
            logger.warning("清空历史失败 %s: %s", path, e)
