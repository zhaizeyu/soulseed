"""
图片压缩、音频格式转换、人设与世界书加载等本地 I/O 辅助函数。
"""
import json
from pathlib import Path
from typing import Any

# 资源路径（相对于项目根）
_ASSETS = Path(__file__).resolve().parents[2] / "assets"
PERSONAS_DIR = _ASSETS / "personas"
WORLD_BOOKS_DIR = _ASSETS / "world_books"
DEFAULT_PERSONA = "vedal_main.json"


def load_persona(name: str = DEFAULT_PERSONA) -> dict[str, Any]:
    """
    从 assets/personas/ 加载人设 JSON。
    返回包含 system_instruction、name、behavior_rules 等字段的字典。
    """
    path = PERSONAS_DIR / (name if name.endswith(".json") else f"{name}.json")
    if not path.exists():
        return {"system_instruction": "", "name": "", "behavior_rules": []}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def list_world_books() -> list[str]:
    """
    列出 assets/world_books/ 下所有 .json 文件名（含扩展名）。
    供后续按需加载或组装提示词时选用。
    """
    if not WORLD_BOOKS_DIR.exists():
        return []
    return sorted(p.name for p in WORLD_BOOKS_DIR.glob("*.json"))


def load_world_book(name: str) -> dict[str, Any]:
    """
    从 assets/world_books/ 加载世界书 JSON。
    格式通常包含 name、description、entries（key/content 等），用于关键词触发注入。
    name 可为文件名或带 .json 的完整名。
    """
    path = WORLD_BOOKS_DIR / (name if name.endswith(".json") else f"{name}.json")
    if not path.exists():
        return {"name": "", "description": "", "entries": {}}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_world_book_prompt_snippet(
    world_book: dict[str, Any],
    *,
    entry_ids: list[str] | None = None,
    only_enabled: bool = True,
) -> str:
    """
    从已加载的世界书中取出条目的 content，拼成一段文本，供未来组装提示词用。
    - entry_ids: 若指定，只取这些 id 的条目；否则取全部。
    - only_enabled: 是否只取 enabled 且非 disable 的条目。
    """
    entries = world_book.get("entries") or {}
    if isinstance(entries, dict):
        items = list(entries.values()) if entry_ids is None else [entries[e] for e in entry_ids if e in entries]
    else:
        items = entries
    parts = []
    for e in items:
        if not isinstance(e, dict):
            continue
        if only_enabled and (e.get("disable") or not e.get("enabled", True)):
            continue
        content = e.get("content") or ""
        if content.strip():
            parts.append(content.strip())
    return "\n\n".join(parts)


# TODO: 图片压缩、音频格式转换
def compress_image(image: Any, max_size_kb: int = 500) -> bytes:
    """将图片压缩到指定大小以内，返回字节。"""
    return b""


def ensure_audio_format(path: Path, target_format: str = "wav") -> Path:
    """确保音频为 target_format，必要时转换并返回新路径。"""
    return path
