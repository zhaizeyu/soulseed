"""
从 Langfuse Prompt Management 拉取系统提示词。

逻辑名由 ``assets/prompts/langfuse_prompts.json`` 映射到 Langfuse 中的 prompt 名，
可选 ``LANGFUSE_PROMPT_MAP_KEY`` 选择条目（默认 ``system``）。
"""
from __future__ import annotations

from typing import Any

from src.core.config_loader import get_config
from src.core.logger import get_logger
from src.llm_gateway.prompt_mapping import resolve_langfuse_prompt_target

logger = get_logger(__name__)


def _truthy(val: Any, default: bool = True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("0", "false", "no", "off"):
        return False
    if s in ("1", "true", "yes", "on"):
        return True
    return default


def _compiled_to_system_string(prompt_obj: Any, *, prompt_type: str) -> str:
    compiled: Any = None
    try:
        compiled = prompt_obj.compile()
    except TypeError:
        try:
            compiled = prompt_obj.compile({})
        except Exception:
            compiled = None
    except Exception:
        try:
            compiled = prompt_obj.compile({})
        except Exception:
            compiled = None

    if isinstance(compiled, str) and compiled.strip():
        return compiled.strip()

    if isinstance(compiled, list):
        parts: list[str] = []
        for item in compiled:
            if not isinstance(item, dict):
                continue
            role = str(item.get("role") or "").strip().lower()
            content = item.get("content")
            if content is None:
                continue
            if prompt_type == "chat" and role and role != "system":
                continue
            parts.append(str(content).strip())
        text = "\n\n".join(p for p in parts if p)
        if text:
            return text

    raw = getattr(prompt_obj, "prompt", None)
    if isinstance(raw, str) and raw.strip():
        return raw.strip()
    if isinstance(raw, list):
        buf: list[str] = []
        for item in raw:
            if isinstance(item, dict) and str(item.get("role", "")).lower() == "system":
                c = item.get("content")
                if c is not None:
                    buf.append(str(c).strip())
        return "\n\n".join(x for x in buf if x).strip()
    return ""


def _get_prompt_object(lf: Any, name: str, label: str | None, explicit_type: str | None) -> tuple[Any, str] | None:
    """按 label/type 优先顺序调用 get_prompt，返回 (prompt_obj, 用于 compile 的 type)。"""
    if not (name or "").strip():
        return None
    et = explicit_type if explicit_type in ("text", "chat") else None
    trials: list[tuple[dict[str, Any], str]] = []
    if label and et:
        trials.append(({"label": label, "type": et}, et))
    elif et:
        trials.append(({"type": et}, et))
    if label:
        trials.append(({"label": label}, "text"))
    trials.append(({}, "text"))
    if et != "chat":
        trials.append(({"type": "chat"}, "chat"))

    seen: set[frozenset[tuple[str, Any]]] = set()
    for kwargs, ptype in trials:
        fk = frozenset(kwargs.items())
        if fk in seen:
            continue
        seen.add(fk)
        try:
            prompt = lf.get_prompt(name, **kwargs) if kwargs else lf.get_prompt(name)
            return prompt, ptype
        except TypeError:
            if "type" in kwargs:
                slim = {k: v for k, v in kwargs.items() if k != "type"}
                try:
                    prompt = lf.get_prompt(name, **slim) if slim else lf.get_prompt(name)
                    return prompt, "text"
                except Exception:
                    continue
            continue
        except Exception as e:
            logger.debug("Langfuse get_prompt(%r, **%s): %s", name, kwargs, e)
            continue
    return None


def fetch_langfuse_system_prompt() -> str | None:
    """
    使用 Langfuse 拉取系统提示词文本。

    依赖：LANGFUSE_PUBLIC_KEY、LANGFUSE_SECRET_KEY、LANGFUSE_HOST（或 LANGFUSE_BASE_URL）。
    提示名由 ``assets/prompts/langfuse_prompts.json`` 与 ``LANGFUSE_PROMPT_MAP_KEY`` 解析。
    """
    cfg = get_config()
    if not _truthy(cfg.get("LANGFUSE_SYSTEM_PROMPT_ENABLED"), default=True):
        return None

    pub = str(cfg.get("LANGFUSE_PUBLIC_KEY") or "").strip()
    sec = str(cfg.get("LANGFUSE_SECRET_KEY") or "").strip()
    if not pub or not sec:
        return None

    name, label, explicit_type = resolve_langfuse_prompt_target(cfg)
    if not (name or "").strip():
        logger.warning("Langfuse 提示词名未解析到：检查 assets/prompts/langfuse_prompts.json 与 LANGFUSE_PROMPT_MAP_KEY")
        return None

    try:
        from langfuse import Langfuse
    except ImportError:
        logger.warning("未安装 langfuse，跳过从 Langfuse 拉取系统提示词")
        return None

    lf = Langfuse()
    got = _get_prompt_object(lf, name, label, explicit_type)
    if got is None:
        logger.warning("Langfuse get_prompt 全部尝试失败: name=%s label=%s", name, label)
        return None

    prompt_obj, resolved_type = got
    text = _compiled_to_system_string(prompt_obj, prompt_type=resolved_type)
    if text:
        return text

    logger.warning("Langfuse 提示词已拉取但编译结果为空: name=%s", name)
    return None
