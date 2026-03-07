"""
统一用户回合输入 — 将文本、图片、语音、附件等抽象为单一对象，便于多端扩展。
后续 Telegram 图片/语音、Web 上传文件、CLI 本地图片等均可通过同一结构传入，无需再改函数签名。
"""
from dataclasses import dataclass
from typing import Any


@dataclass
class UserTurnInput:
    """单轮用户输入的统一结构。各字段可选，至少应有 text 或后续扩展的音频/图片内容。"""
    text: str | None = None
    """本回合文本（或 STT 转写后的文本）。"""
    images: list[Any] | None = None
    """本回合图片列表，元素可为路径 (str) 或已加载的图片对象 (如 PIL.Image)。首张会作为 vision 传入主脑。"""
    audio_path: str | None = None
    """本回合语音文件路径，后续可在此做 STT 转写并合并到 text 或单独传入。"""
    metadata: dict[str, Any] | None = None
    """扩展字段，如来源端、附件类型等，不参与主脑推理，可参与记忆 metadata。"""

    def effective_text(self) -> str:
        """供检索与主脑使用的文本：当前仅 text，后续可合并 audio 转写结果。"""
        return (self.text or "").strip()
