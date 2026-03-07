"""
提示词组装 — 按 prompt.md 顺序拼接：Jailbreak → 用户信息 → 角色卡 → 示例对话 → Mem0 → 历史对话 → 眼睛与耳朵 → 当前用户 → Task。
数据来源：assets/prompts/*.json、persona、运行时 mem0/历史/感知/用户输入。
"""
import json
import re
from pathlib import Path
from typing import Any

from src.utils.io_utils import load_persona

# 资源路径
_ASSETS = Path(__file__).resolve().parents[2] / "assets"
PROMPTS_DIR = _ASSETS / "prompts"


def _load_json(name: str) -> dict[str, Any]:
    """加载 assets/prompts/{name}.json。"""
    path = PROMPTS_DIR / f"{name}.json"
    if not path.exists():
        return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jailbreak() -> str:
    """加载 Jailbreak 文案（绝对头部）。"""
    d = _load_json("jailbreak")
    return d.get("content", "")


def load_task() -> str:
    """加载 Task 输出风格限制（绝对底部）。"""
    d = _load_json("task")
    return d.get("content", "")


def load_user_info() -> str:
    """加载用户身份描述。"""
    d = _load_json("user_info")
    return d.get("content", "")


def load_prompt_defaults() -> dict[str, Any]:
    """加载默认的 mem0、chat_history、vision_audio（初始/测试用）。"""
    d = _load_json("prompt_defaults")
    return {
        "mem0": d.get("mem0", []),
        "chat_history": d.get("chat_history", []),
        "vision_audio": d.get("vision_audio", ""),
    }


def _persona_data(persona: dict[str, Any]) -> dict[str, Any]:
    """兼容 chara_card (data.*) 与扁平 persona。"""
    if "data" in persona:
        return persona["data"]
    return persona


def _parse_mes_example(mes_example: str) -> list[dict[str, Any]]:
    """解析 mes_example（{{user}}: ... \\n{{char}}: ...）为带 name 的 system 消息列表。"""
    if not (mes_example or "").strip():
        return []
    out: list[dict[str, Any]] = []
    # 按 {{user}}: 或 {{char}}: 分割，保留顺序
    parts = re.split(r"\s*(\{\{user\}\}:|\{\{char\}\}:)\s*", mes_example.strip())
    i = 1
    while i < len(parts):
        tag = parts[i].strip().lower()
        content = (parts[i + 1] if i + 1 < len(parts) else "").strip()
        i += 2
        if "user" in tag and content:
            out.append({"role": "system", "content": content, "name": "example_user"})
        elif "char" in tag and content:
            out.append({"role": "system", "content": content, "name": "example_assistant"})
    return out


def build_messages(
    *,
    persona_name: str = "vedal_main",
    user_info: str | None = None,
    mem0_lines: list[dict[str, Any]] | None = None,
    chat_history: list[dict[str, str]] | None = None,
    vision_audio_text: str | None = None,
    vision_image_attached: bool = False,
    current_user_input: str = "",
    use_defaults_for_missing: bool = True,
) -> list[dict[str, Any]]:
    """
    按 prompt.md 顺序组装完整消息列表，可直接送入 Chat API。
    与 prompt.md 对应关系：1→Jailbreak 2→User Info+角色卡 3→Example Chat 4→History Memory
    5→Start Chat 6→Vision And Audio 7→用户当前回合(为空则不插入) 8→Task。

    - persona_name: 角色卡文件名（不含 .json），对应 assets/personas/
    - user_info: 用户身份描述，缺省则从 user_info.json 读取
    - mem0_lines: Mem0 检索到的记忆片段列表（含 metadata），缺省则用 prompt_defaults 或空
    - chat_history: 历史对话 [{role, content}, ...]
    - vision_audio_text: 当前耳朵/环境摘要文本，有则插入 §6
    - vision_image_attached: 本回合是否附屏幕截图（有则 §6 插入「读取屏幕截图」说明，图片由调用方随用户消息多模态传入）
    - current_user_input: 当前用户本回合输入
    - use_defaults_for_missing: 若 mem0/chat_history 未传且为 None/空，是否用 prompt_defaults 填充
    """
    persona = load_persona(persona_name if persona_name.endswith(".json") else f"{persona_name}.json")
    data = _persona_data(persona)
    name = data.get("name", "")
    description = data.get("description", "")
    personality = data.get("personality", "")
    scenario = data.get("scenario", "")
    mes_example = data.get("mes_example", "")

    if user_info is None:
        user_info = load_user_info()
    if mem0_lines is None and use_defaults_for_missing:
        defaults = load_prompt_defaults()
        # 兼容旧版字符串列表
        raw_mem0 = defaults.get("mem0", []) or []
        mem0_lines = [{"memory": m} if isinstance(m, str) else m for m in raw_mem0]
    if mem0_lines is None:
        mem0_lines = []
    if chat_history is None and use_defaults_for_missing:
        defaults = load_prompt_defaults()
        chat_history = defaults.get("chat_history", []) or []
    if chat_history is None:
        chat_history = []
    # 环境感知仅在有真实传入时插入（主流程 orchestrator 当前恒传 None/空，不读默认，避免插假数据）
    if vision_audio_text is None:
        vision_audio_text = ""

    jailbreak = load_jailbreak()
    task = load_task()

    messages: list[dict[str, Any]] = []

    # 1. 越狱与核心规则 (prompt.md §1)
    if jailbreak:
        messages.append({"role": "system", "content": jailbreak})

    # 2. 角色卡-身份与世界观：User Info + name/description/personality/scenario (prompt.md §2)
    if user_info:
        messages.append({"role": "system", "content": user_info})
    if name and description:
        messages.append({"role": "system", "content": f"{name}：{description}"})
    elif description:
        messages.append({"role": "system", "content": description})
    if personality:
        messages.append({"role": "system", "content": personality})
    for part in (s.strip() for s in (scenario or "").split("。") if s.strip()):
        messages.append({"role": "system", "content": part + "。"})

    # 3. 示例对话 (prompt.md §3)
    messages.append({"role": "system", "content": "[Example Chat]"})
    for msg in _parse_mes_example(mes_example):
        messages.append(msg)

    # 4. 潜意识记忆 (prompt.md §4)
    messages.append({"role": "system", "content": "[History Memory]"})
    for item in mem0_lines:
        if isinstance(item, str):
            line = item.strip()
            meta = {}
        else:
            line = str(item.get("memory", "")).strip()
            meta = item.get("metadata", {})

        if line:
            # 💡 记忆有温度：根据元数据组装带情感的记忆片段
            user_emo = meta.get("user_emotion") if meta else None
            ai_emo = meta.get("ai_emotion") if meta else None
            time_ctx = meta.get("time_context") if meta else None
            importance = meta.get("importance") if meta else None
            
            prefix = ""
            if time_ctx:
                prefix += f"({time_ctx}) "
            if user_emo or ai_emo:
                emo_str = []
                if user_emo: emo_str.append(f"你当时很{user_emo}")
                if ai_emo: emo_str.append(f"我当时很{ai_emo}")
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

    # 5. 历史对话 (prompt.md §5)
    messages.append({"role": "system", "content": "[Start Chat]"})
    for turn in chat_history:
        role = turn.get("role", "user")
        content = (turn.get("content") or "").strip()
        if content and role in ("user", "assistant"):
            messages.append({"role": role, "content": content})

    # 6. 环境感知 (prompt.md §6)：屏幕截图说明 / 耳朵摘要；图片由调用方随本回合 user 消息传入
    if vision_image_attached or (vision_audio_text and vision_audio_text.strip()):
        messages.append({"role": "system", "content": "[Vision And Audio]"})
        if vision_image_attached:
            messages.append({"role": "system", "content": "附图视为当前看到的画面。"})
        if vision_audio_text and vision_audio_text.strip():
            messages.append({"role": "system", "content": vision_audio_text.strip()})

    # 7. 用户当前回合 (prompt.md §7)：有输入则用输入，无输入则用「继续说话」占位，保证本回合有一条 user
    if (current_user_input or "").strip():
        messages.append({"role": "user", "content": current_user_input.strip()})
    else:
        messages.append({"role": "user", "content": "(请根据上文以角色身份继续说话。)"})

    # 8. 输出风格限制 (prompt.md §8)
    if task:
        messages.append({"role": "system", "content": task})

    return messages


if __name__ == "__main__":
    """命令行：组装并打印或写入 JSON，便于与 docs/prompt.json 对比。"""
    import sys
    msgs = build_messages(
        current_user_input="今天天气真好",
        use_defaults_for_missing=True,
    )
    out_path = Path(__file__).resolve().parents[2] / "docs" / "assembled_prompt.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(msgs, f, ensure_ascii=False, indent=2)
    print("Wrote", len(msgs), "messages to", out_path)
    if "--print" in sys.argv:
        print(json.dumps(msgs, ensure_ascii=False, indent=2))
