#!/usr/bin/env python3
"""
根据当前存储的历史、Mem0、配置与 assets/prompts 还原「最后一次」完整提示词并输出。
用于调试与查看实际发给模型的消息结构。

用法（在项目根目录执行，建议使用项目 venv）：
  .venv/bin/python scripts/inspect_last_prompt.py
  .venv/bin/python scripts/inspect_last_prompt.py --session 8103409829
  .venv/bin/python scripts/inspect_last_prompt.py --session 8103409829 --out last_prompt.json

说明：
  - 默认 session 为 CLI/Web 的默认会话（chat_history_file）。
  - --session 8103409829 等价于 tg_8103409829（Telegram 会话）。
  - 「最后一次」指：若历史最后一条是 assistant，则还原生成该条时的提示；若最后一条是 user，则还原若此时生成回复会用到的提示。
  - Mem0 会按当前 query 实时检索一次，与真实回合可能略有差异（若 Mem0 有更新）。
"""
import argparse
import asyncio
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _parse_session(session: str) -> str:
    if not session or session == "default":
        return ""
    s = session.strip()
    if s.startswith("tg_"):
        return s
    return f"tg_{s}"


async def _get_mem0_lines(query: str, session_id: str) -> list:
    from src.brain import memory as memory_module
    from src.core.config_loader import get_config
    cfg = get_config()
    limit = max(1, int(cfg.get("mem0_search_limit", 5)))
    mem0_user_id = session_id if session_id else "default"
    return await memory_module.search(
        query or "(无文字)",
        top_k=limit,
        user_id=mem0_user_id,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="还原最后一次完整提示词并输出")
    parser.add_argument(
        "--session",
        default="default",
        help="会话：default（CLI/Web）或 Telegram chat_id（如 8103409829），自动补 tg_ 前缀",
    )
    parser.add_argument(
        "--out",
        default="",
        help="将提示词 JSON 写入该文件；不指定则打印到 stdout",
    )
    args = parser.parse_args()

    session_id = _parse_session(args.session)
    if session_id:
        session_label = session_id
    else:
        session_label = "default"

    from src.brain.chat_history_store import load_history
    from src.brain.prompt_assembler import build_messages
    history = load_history(session_id)
    if not history:
        print(f"[{session_label}] 无历史记录，无法还原提示词。", file=sys.stderr)
        return 1

    # 最后一条
    last = history[-1]
    last_role = last.get("role", "")
    if last_role == "assistant":
        # 还原「生成最后这条 assistant」时的提示：历史不包含最后这一对 user+assistant
        history_for_build = history[:-2]
        current_user_input = (history[-2].get("content") or "").strip()
        vision_image_attached = bool((history[-2].get("image_path") or "").strip())
    else:
        # 最后一条是 user：还原「若现在生成回复」会用到的提示
        history_for_build = history[:-1]
        current_user_input = (last.get("content") or "").strip()
        vision_image_attached = bool((last.get("image_path") or "").strip())

    query = current_user_input or "(无文字)"
    mem0_lines = asyncio.run(_get_mem0_lines(query, session_id))

    messages = build_messages(
        mem0_lines=mem0_lines or None,
        chat_history=history_for_build,
        vision_audio_text=None,
        vision_image_attached=vision_image_attached,
        current_user_input=current_user_input,
    )

    out = json.dumps(messages, ensure_ascii=False, indent=2)
    if args.out:
        Path(args.out).write_text(out, encoding="utf-8")
        print(f"已写入 {len(messages)} 条消息 -> {args.out}", file=sys.stderr)
    else:
        print(out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
