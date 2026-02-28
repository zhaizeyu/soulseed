"""
FastAPI 对话 API — 与 main.py 调度器解耦，仅依赖 ConversationService。
提供流式 SSE 与可选非流式接口；CORS 开放供前端调用。
Web 模式含眼睛心跳：后台定时截图对比，有变化则自动执行一轮主动说话并写入历史（前端轮询 /api/history 可见）。
"""
import asyncio
import json
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, File, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from pydantic import BaseModel

from src.core.config_loader import get_config
from src.core.logger import get_logger, get_log_path
from src.web.service import ConversationService, HEARTBEAT_PROACTIVE_PROMPT
from src.brain import memory as memory_module
from src.brain.chat_history_store import load_history
from src.senses import vision as vision_module
from src.senses import hearing as hearing_module
from src.expression import mouth as mouth_module

logger = get_logger(__name__)

_heartbeat_task: asyncio.Task | None = None


async def _heartbeat_loop() -> None:
    """Web 模式后台任务：每 N 秒心跳检测，有变化则执行主动回合并写入历史。"""
    config = get_config()
    loop = asyncio.get_event_loop()
    while True:
        try:
            interval = max(1, int(config.get("vision_heartbeat_interval_sec", 30)))
        except (TypeError, ValueError):
            interval = 30
        await asyncio.sleep(interval)
        if not config.get("vision_heartbeat_enabled", False):
            continue
        try:
            triggered, image = await loop.run_in_executor(None, vision_module.check_heartbeat)
            if not triggered or image is None:
                continue
            logger.info("[Web] 心跳触发主动说话，开始本轮生成")
            service = get_service()
            full_reply: list[str] = []
            try:
                async for chunk in service.run_one_turn(HEARTBEAT_PROACTIVE_PROMPT, vision_image_override=image):
                    full_reply.append(chunk)
            except Exception as e:
                logger.exception("[Web] 心跳回合主脑异常: %s", e)
                full_reply.append(f"[错误: {e}]")
            reply_text = "".join(full_reply).strip()
            service.commit_turn(HEARTBEAT_PROACTIVE_PROMPT, reply_text)
            if reply_text:
                await memory_module.add_background(None, reply_text)
            logger.info("[Web] 心跳主动回合已写入历史")
        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.warning("Web 心跳检测异常: %s", e, exc_info=True)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动时打日志并启动心跳任务；关闭时取消任务。"""
    global _heartbeat_task
    config = get_config()
    log_path = get_log_path()
    logger.info("Web 模式启动（日志: %s）", log_path)
    hb_enabled = config.get("vision_heartbeat_enabled", False)
    hb_interval = config.get("vision_heartbeat_interval_sec", 30)
    if hb_enabled:
        logger.info("眼睛心跳: 已开启，每 %s 秒检测画面变化，有变化则主动说话并写入历史（前端轮询 /api/history 可见）", hb_interval)
        _heartbeat_task = asyncio.create_task(_heartbeat_loop())
    else:
        logger.info("眼睛心跳: 未开启 (vision_heartbeat_enabled=false)")
    yield
    if _heartbeat_task is not None:
        _heartbeat_task.cancel()
        try:
            await _heartbeat_task
        except asyncio.CancelledError:
            pass
        _heartbeat_task = None
    logger.info("Web 模式已停止")


app = FastAPI(
    title="VedalAI Chat API",
    description="数字生命对话接口，与 CLI 调度器解耦",
    version="0.1.0",
    lifespan=lifespan,
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


class TtsRequest(BaseModel):
    text: str = ""


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


@app.get("/api/config")
async def get_client_config():
    """返回前端所需配置（如是否开启语音回复），不暴露敏感项。"""
    cfg = get_config()
    return {
        "tts_reply_enabled": bool(cfg.get("tts_reply_enabled", True)),
    }


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


@app.post("/api/speech-to-text")
async def speech_to_text_api(audio: UploadFile = File(...)):
    """
    语音转文本：上传一段音频（webm/mp3/wav 等），返回识别文本。
    请求：multipart/form-data，字段名 audio，文件为浏览器 MediaRecorder 等录制的音频。
    响应：{"text": "识别结果"}，使用 Gemini 转写（与主脑共用 GEMINI_API_KEY）；失败或未配置时 text 可为空。
    """
    try:
        body = await audio.read()
        filename = audio.filename or "audio.webm"
    except Exception as e:
        logger.warning("读取上传音频失败: %s", e)
        return {"text": ""}
    loop = asyncio.get_event_loop()
    text = await loop.run_in_executor(
        None,
        lambda: hearing_module.speech_to_text(body, filename),
    )
    return {"text": text}


@app.post("/api/tts")
async def tts_api(request: TtsRequest):
    """
    TTS：将文本合成为语音，返回 mp3 音频流。
    请求体：{"text": "要读的句子"}。用于前端播报助手回复中的「说的话」。
    """
    audio_bytes = await mouth_module.text_to_speech_async(request.text or "")
    if not audio_bytes:
        return Response(content=b"", status_code=200, media_type="audio/mpeg")
    return Response(content=audio_bytes, media_type="audio/mpeg")
