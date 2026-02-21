"""
主脑 — 封装 Gemini API，处理多模态上下文与对话会话管理。
实例化 gemini-3-flash-preview，加载 vedal_main.json 为 system_instruction；
注册 tools_registry 并开启 enable_automatic_function_calling；
接收 (user_text, image_obj)，先查 memory 再 ChatSession.send_message_async(stream=True)，返回文本流生成器。
"""
import asyncio
from typing import Any, AsyncIterator

# TODO: 实现 Gemini ChatSession、思考模型、记忆融合
async def chat_stream(user_text: str, image_obj: Any = None) -> AsyncIterator[str]:
    """接收用户文本与可选图像，yield 主脑回复文本流。"""
    yield ""
    await asyncio.sleep(0)
