"""
统一的底层异步 HTTP 请求封装，带重试机制。
"""
import asyncio
from typing import Any, Optional

# TODO: aiohttp + 重试、超时、统一错误处理
async def request(
    method: str,
    url: str,
    *,
    json: Optional[dict[str, Any]] = None,
    headers: Optional[dict[str, str]] = None,
    timeout: float = 30.0,
) -> dict[str, Any] | bytes:
    """发送异步 HTTP 请求，返回 JSON 或 bytes。"""
    return {}
