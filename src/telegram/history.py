"""
Telegram 会话历史 — 委托给统一存储层 chat_history_store，与 Web/CLI 同格式（timestamp、image_path）。
仅做 session_id 映射：get(chat_id) / append(chat_id, ...) 内部调用 load_history(session_id="tg_{chat_id}") / append_turns(..., session_id="tg_{chat_id}")。
"""
from typing import Any

from src.brain.chat_history_store import load_history, append_turns, clear_history


def get(chat_id: int | str) -> list[dict[str, Any]]:
    """加载该会话历史，返回最近 N 条（含 timestamp、image_path）。"""
    return load_history(session_id=f"tg_{chat_id}")


def append(
    chat_id: int | str,
    user_content: str,
    assistant_content: str,
    user_image: Any = None,
) -> None:
    """追加一轮 user + assistant；若本回合用户发了图则传 user_image（PIL.Image），会落盘并带时间戳。"""
    turns: list[dict[str, Any]] = []
    if user_content or user_image is not None:
        user_turn: dict[str, Any] = {"role": "user", "content": user_content or ""}
        if user_image is not None:
            user_turn["image"] = user_image
        turns.append(user_turn)
    turns.append({"role": "assistant", "content": assistant_content})
    append_turns(turns, session_id=f"tg_{chat_id}")


def clear(chat_id: int | str) -> None:
    """清空该会话的上下文窗口历史（不删 Mem0 记忆）。"""
    clear_history(session_id=f"tg_{chat_id}")
