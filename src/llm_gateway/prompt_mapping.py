"""
assets/prompts/langfuse_prompts.json — 逻辑 key → Langfuse prompt（name / 可选 label、type）。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_MAP_PATH = _PROJECT_ROOT / "assets" / "prompts" / "langfuse_prompts.json"


def load_langfuse_prompt_map() -> dict[str, Any]:
    if not _MAP_PATH.exists():
        return {}
    try:
        with open(_MAP_PATH, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def parse_map_entry(raw: Any) -> tuple[str, str | None, str | None]:
    if isinstance(raw, str) and raw.strip():
        return raw.strip(), None, None
    if isinstance(raw, dict):
        name = str(raw.get("name") or raw.get("langfuse") or raw.get("prompt") or "").strip()
        label = str(raw.get("label") or "").strip() or None
        ptype = str(raw.get("type") or "").strip().lower() or None
        if ptype not in ("text", "chat"):
            ptype = None
        if name:
            return name, label, ptype
    return "", None, None


def resolve_langfuse_prompt_target(cfg: dict[str, Any], *, logical_key: str | None = None) -> tuple[str, str | None, str | None]:
    key = (logical_key or str(cfg.get("LANGFUSE_PROMPT_MAP_KEY") or "system")).strip() or "system"
    m = load_langfuse_prompt_map()
    if key not in m:
        return "", None, None
    return parse_map_entry(m[key])
