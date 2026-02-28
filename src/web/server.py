"""
FastAPI 对话 API — 与 main.py 调度器解耦，仅依赖 ConversationService。
提供流式 SSE 与可选非流式接口；CORS 开放供前端调用。
"""
import json
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from src.web.service import ConversationService
from src.brain import memory as memory_module
from src.brain.chat_history_store import load_history

app = FastAPI(
    title="VedalAI Chat API",
    description="数字生命对话接口，与 CLI 调度器解耦",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 单例服务；可选改为依赖注入
_service: ConversationService | None = None


def get_service() -> ConversationService:
    global _service
    if _service is None:
        _service = ConversationService()
    return _service


class ChatRequest(BaseModel):
    message: str = ""


def _sse_line(data: dict) -> str:
    return f"data: {json.dumps(data, ensure_ascii=False)}\n\n"


async def _stream_reply(message: str) -> AsyncIterator[str]:
    """流式生成 SSE 行，并在结束后写入历史与长期记忆。"""
    service = get_service()
    full_reply: list[str] = []
    try:
        async for chunk in service.run_one_turn(message):
            full_reply.append(chunk)
            yield _sse_line({"chunk": chunk, "done": False})
    except Exception as e:
        full_reply.append(f"[错误: {e}]")
        yield _sse_line({"chunk": f"[错误: {e}]", "done": False})
    reply_text = "".join(full_reply).strip()
    service.commit_turn(message, reply_text)
    if reply_text:
        await memory_module.add_background(message.strip() or None, reply_text)
    yield _sse_line({"chunk": None, "done": True})


@app.get("/")
async def root():
    return {"service": "VedalAI Chat API", "docs": "/docs"}


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.get("/api/history")
async def get_history():
    """返回当前对话历史，与 CLI 共用唯一数据源（config chat_history_file）；前端仅展示，不覆盖后端。"""
    return {"messages": load_history()}


@app.post("/api/chat")
async def chat_stream(request: ChatRequest):
    """
    流式对话：请求体 { "message": "用户输入" }，响应为 SSE 流。
    每行: data: {"chunk": "片段", "done": false}，结束: data: {"chunk": null, "done": true}
    """
    message = (request.message or "").strip()
    # 空输入按「继续说话」处理，与 CLI 一致
    return StreamingResponse(
        _stream_reply(message),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/chat/sync")
async def chat_sync(request: ChatRequest):
    """非流式对话：等待完整回复后一次性返回。"""
    message = (request.message or "").strip()
    service = get_service()
    full_reply: list[str] = []
    try:
        async for chunk in service.run_one_turn(message):
            full_reply.append(chunk)
    except Exception as e:
        full_reply.append(f"[错误: {e}]")
    reply_text = "".join(full_reply).strip()
    service.commit_turn(message, reply_text)
    if reply_text:
        await memory_module.add_background(message.strip() or None, reply_text)
    return {"reply": reply_text}
