"""
将助手回复按「场景 / 心理 / 说的话」分段并转为 Telegram HTML。
- 语言（说的话）：<b>角色名：</b>"内容"
- 心理描写：（ ）/（ ）内 → <i>内容</i>
- 场景：仅转义
"""
import html
from dataclasses import dataclass
from typing import Literal

SegmentType = Literal["narrative", "thought", "speech"]

DEFAULT_SPEAKER_NAME = "Kurisu"


@dataclass
class ContentSegment:
    type: SegmentType
    text: str


def _find_matching_paren(s: str, after_open: int, open_ch: str, close_ch: str) -> int:
    depth = 1
    for i in range(after_open, len(s)):
        if s[i] == open_ch:
            depth += 1
        elif s[i] == close_ch:
            depth -= 1
            if depth == 0:
                return i
    return -1


# 与 webapp/src/lib/format-content.ts 一致：括号与引号对
_PAIRS = [
    ("(", ")", "thought", True),       # 英文括号，支持嵌套
    ("\uFF08", "\uFF09", "thought", True),  # （）
    ("\u300C", "\u300D", "speech", False),  # 「」
    ('"', '"', "speech", False),
    ("\u201C", "\u201D", "speech", False),  # " "
]


def parse_content_segments(content: str) -> list[ContentSegment]:
    if not content:
        return []
    segments: list[ContentSegment] = []
    pos = 0

    while pos < len(content):
        next_idx = len(content)
        chosen = _PAIRS[0]
        for p in _PAIRS:
            open_s, close_s, seg_type, nested = p[0], p[1], p[2], p[3]
            i = content.find(open_s, pos)
            if i != -1 and i < next_idx:
                next_idx = i
                chosen = (open_s, close_s, seg_type, nested)

        if next_idx > pos:
            segments.append(ContentSegment("narrative", content[pos:next_idx]))
        if next_idx == len(content):
            break

        open_s, close_s, seg_type, nested = chosen
        pos = next_idx + len(open_s)
        if nested:
            close_idx = _find_matching_paren(content, pos, open_s, close_s)
        else:
            close_idx = content.find(close_s, pos)
        if close_idx == -1:
            segments.append(ContentSegment("narrative", content[next_idx:]))
            break
        inner_text = content[pos:close_idx]
        # 双引号内去掉空格后字数 < 5 按场景渲染（与 Web 一致）
        is_short_quoted = (
            seg_type == "speech" and len(inner_text.replace(" ", "").replace("\n", "")) < 5
        )
        actual_type: SegmentType = "narrative" if is_short_quoted else seg_type
        segments.append(ContentSegment(actual_type, inner_text))
        pos = close_idx + len(close_s)

    return segments


def format_reply_to_telegram_html(text: str, *, speaker_name: str = DEFAULT_SPEAKER_NAME) -> str:
    """
    将主脑返回的纯文本分段，转为 Telegram HTML：
    - 说的话 → <b>角色名：</b>"内容"
    - 心理 → <i>内容</i>
    - 场景 → 仅转义
    用于 send_message(..., parse_mode="HTML")。
    """
    if not text:
        return ""
    segments = parse_content_segments(text)
    speaker_escaped = html.escape(speaker_name)
    out: list[str] = []
    for seg in segments:
        escaped = html.escape(seg.text)
        if seg.type == "speech":
            out.append(f'<b>{speaker_escaped}："{escaped}"</b>')
        elif seg.type == "thought":
            out.append(f"<i>{escaped}</i>")
        else:
            out.append(escaped)
    return "".join(out)
