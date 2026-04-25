"""
提示词组装 — 运行时上下文（记忆/历史/感知/当前用户）。
系统提示词仅由 Langfuse 提供，见 ``load_system_prompt()``；主脑将其作为 ``system_instruction`` 注入。

约定：与主对话相关的上下文消息只在本文件组装；其它模块调用 ``build_messages`` / ``load_system_prompt``，
不得在别处拼接发给模型的 system/user 顺序。
"""
from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

_WEEKDAY = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")


def _now_for_prompt() -> datetime:
    """按配置的 IANA 时区取「墙钟现在」；未配置或非法时退回本机本地时区。"""
    from src.core.config_loader import get_config

    cfg = get_config()
    name = str(cfg.get("app_timezone") or cfg.get("APP_TIMEZONE") or "").strip()
    if name:
        try:
            return datetime.now(ZoneInfo(name))
        except Exception:
            pass
    return datetime.now().astimezone()


def _get_current_time_readable() -> str:
    """返回带时区与 ISO 的当前时间，供环境感知注入，减少模型臆造时刻。"""
    now = _now_for_prompt()
    wd = _WEEKDAY[now.weekday()]
    h, m = now.hour, now.minute
    if h < 6:
        period = "凌晨"
    elif h < 12:
        period = "上午"
    elif h < 18:
        period = "下午"
    else:
        period = "晚上"
    # 使用 24 小时制，避免「晚上九点」与 12 小时制歧义
    readable = (
        f"{now.year}年{now.month}月{now.day}日 {wd} {period}{h}点{m:02d}分（24小时制为 {h:02d}:{m:02d}）"
    )
    try:
        iso = now.isoformat(timespec="seconds")
    except Exception:
        iso = now.isoformat()
    tz_key = str(now.tzinfo) if now.tzinfo else "local"
    return f"当前时间（{tz_key}）：{readable}。权威时刻 ISO8601：{iso}。回答用户关于「现在几点」类问题时，须与此处一致，勿编造其它时刻。"


def _format_timestamp_for_image(timestamp: str) -> str:
    """将 ISO 或空的时间戳转为可读短格式，供历史图中 [图: 时间] 标记。"""
    if not (timestamp or "").strip():
        return ""
    try:
        ts = timestamp.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return f"{dt.month}月{dt.day}日 {dt.hour}:{dt.minute:02d}"
    except (ValueError, TypeError):
        return (timestamp or "")[:16]


def load_system_prompt() -> str:
    """从 Langfuse 拉取系统提示词；失败返回空字符串。"""
    from src.llm_gateway.langfuse_prompt import fetch_langfuse_system_prompt

    text = fetch_langfuse_system_prompt()
    return (text or "").strip()


def build_messages(
    *,
    mem0_lines: list[dict[str, Any]] | None = None,
    chat_history: list[dict[str, Any]] | None = None,
    vision_audio_text: str | None = None,
    vision_image_attached: bool = False,
    current_user_input: str = "",
) -> list[dict[str, Any]]:
    """
    组装运行时消息列表，可直接送入 Chat API（不含角色系统提示，由主脑单独注入）。

    - mem0_lines: Mem0 检索片段（含 metadata）
    - chat_history: 历史 [{role, content, ...}]
    - vision_audio_text: 耳朵/环境摘要
    - vision_image_attached: 本回合是否附屏幕截图
    - current_user_input: 本回合用户文字
    """
    if mem0_lines is None:
        mem0_lines = []
    if chat_history is None:
        chat_history = []
    if vision_audio_text is None:
        vision_audio_text = ""

    messages: list[dict[str, Any]] = []

    messages.append({"role": "system", "content": "[History Memory]"})
    for item in mem0_lines:
        if isinstance(item, str):
            line = item.strip()
            meta = {}
        else:
            line = str(item.get("memory", "")).strip()
            meta = item.get("metadata", {})

        if line:
            user_emo = meta.get("user_emotion") if meta else None
            ai_emo = meta.get("ai_emotion") if meta else None
            time_ctx = meta.get("time_context") if meta else None
            timestamp = meta.get("timestamp") if meta else None
            importance = meta.get("importance") if meta else None

            prefix = ""
            if timestamp or time_ctx:
                time_part = time_ctx or ""
                if timestamp:
                    try:
                        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
                        time_part = f"{dt.month}月{dt.day}日" + (f" {time_ctx}" if time_ctx else "")
                    except (ValueError, TypeError):
                        time_part = time_part or timestamp[:10]
                prefix += f"({time_part}) "
            if user_emo or ai_emo:
                emo_str = []
                if user_emo:
                    emo_str.append(f"你当时很{user_emo}")
                if ai_emo:
                    emo_str.append(f"我当时很{ai_emo}")
                prefix += f"[{'，'.join(emo_str)}] "

            suffix = ""
            if importance is not None:
                try:
                    if int(importance) >= 8:
                        suffix = " (这是我铭记于心的重要记忆)"
                except (ValueError, TypeError):
                    pass

            formatted_line = f"{prefix}{line}{suffix}"
            messages.append({"role": "system", "content": formatted_line})

    messages.append({"role": "system", "content": "[Start Chat]"})
    for turn in chat_history:
        role = turn.get("role", "user")
        if role not in ("user", "assistant"):
            continue
        content = (turn.get("content") or "").strip()
        image_path = turn.get("image_path")
        if not content and not image_path:
            continue
        timestamp = turn.get("timestamp") or ""
        if image_path and role == "user":
            time_label = _format_timestamp_for_image(timestamp)
            tag = "[图: " + (time_label or "历史") + "]"
            content = (content + "\n" + tag).strip() if content else tag
        msg: dict[str, Any] = {"role": role, "content": content}
        if role == "user" and image_path:
            msg["image_path"] = image_path
        messages.append(msg)

    messages.append({"role": "system", "content": "[Vision And Audio]"})
    messages.append({"role": "system", "content": _get_current_time_readable()})
    if vision_image_attached:
        messages.append(
            {
                "role": "system",
                "content": "紧接着的「用户当前回合」中的附图视为**当前**看到的画面；历史对话里带 [图: 时间] 的为过往某时刻的画面，勿与本回合附图混淆。",
            }
        )
    else:
        messages.append(
            {
                "role": "system",
                "content": "本回合没有新的视觉输入，你不能描述或假装看到「此刻」的用户、屏幕或周围环境。"
                "历史对话和记忆里的过往画面你仍然可以回忆和引用，只是不要把它们说成是「现在看到的」。",
            }
        )
    if vision_audio_text and vision_audio_text.strip():
        messages.append({"role": "system", "content": vision_audio_text.strip()})

    if (current_user_input or "").strip():
        messages.append({"role": "user", "content": current_user_input.strip()})
    else:
        messages.append({"role": "user", "content": "(请根据上文以角色身份继续说话。)"})

    return messages


if __name__ == "__main__":
    msgs = build_messages(current_user_input="今天天气真好")
    out_path = Path(__file__).resolve().parents[2] / "docs" / "assembled_prompt.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False, indent=2)
    print("Wrote", len(msgs), "messages to", out_path)
    if "--print" in sys.argv:
        print(json.dumps(msgs, ensure_ascii=False, indent=2))
