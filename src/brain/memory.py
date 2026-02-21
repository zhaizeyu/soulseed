"""
海马体 — 封装 Mem0，负责长期记忆的异步写入与检索。
配置 OpenAI Embedding + Qdrant/Chroma；提供 search() 与 add_background() 异步方法。
"""
from typing import List

# TODO: 集成 Mem0，实现 search / add_background
async def search(query: str, top_k: int = 5) -> List[str]:
    """根据 query 检索相关长期记忆片段。"""
    return []


async def add_background(content: str) -> None:
    """对话结束后异步提取事实并更新记忆库，不阻塞主回复流。"""
    pass
