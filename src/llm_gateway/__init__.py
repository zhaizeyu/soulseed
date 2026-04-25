"""
llm-gateway 对外入口。
统一封装 LiteLLM 调用与 Langfuse 可观测性。
"""

from src.llm_gateway.langfuse_prompt import fetch_langfuse_system_prompt
from src.llm_gateway.client import (
    build_image_content_part,
    build_mem0_openai_config,
    get_chat_model_name,
    get_embedding_model_name,
    get_gateway_api_base,
    get_gateway_api_key,
    get_stt_model_name,
    speech_to_text,
    stream_chat,
)

__all__ = [
    "fetch_langfuse_system_prompt",
    "stream_chat",
    "speech_to_text",
    "build_image_content_part",
    "get_gateway_api_key",
    "get_gateway_api_base",
    "get_chat_model_name",
    "get_stt_model_name",
    "get_embedding_model_name",
    "build_mem0_openai_config",
]
