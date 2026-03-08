"""
命令与消息处理：/start、/help、/clear；文本消息；语音消息；图片消息（下载 → 作为 vision 传入主脑）。
"""
import asyncio
import io

from telegram import Update
from telegram.ext import ContextTypes

from src.core.config_loader import get_config
from src.core.logger import get_logger
from src.brain.turn_input import UserTurnInput
from src.senses import hearing
from src.senses import vision as vision_module

from src.telegram import service as tg_service
from src.telegram.format_reply import format_reply_to_telegram_html

logger = get_logger(__name__)


async def _send_reply(update: Update, text: str) -> None:
    """发送助手回复：语言 <b>角色名：</b>"…"、心理 <i>…</i>、场景纯文本；失败则回退纯文本。"""
    if not update.message:
        return
    msg = text or "（无回复）"
    speaker = (get_config().get("telegram_speaker_name") or "").strip() or None
    try:
        html_msg = format_reply_to_telegram_html(msg, speaker_name=speaker or "Kurisu")
        await update.message.reply_text(html_msg, parse_mode="HTML")
    except Exception as e:
        logger.debug("Telegram HTML 渲染失败，回退纯文本: %s", e)
        await update.message.reply_text(msg)

WELCOME = "你好，我是 SoulSeed。发文字、语音或图片都可以，我会记住我们的对话。"
HELP_TEXT = "发送文字、语音或图片与我对话。\n/clear 清空当前会话的上下文（记忆保留）。"
CLEAR_DONE = "已清空本会话历史，记忆仍在。"
VOICE_EMPTY = "没听清，再说一次吧～"
PHOTO_FAIL = "图片下载或解析失败，请重试。"
IMAGE_ONLY_PROMPT = "（用户发来一张图片，请根据图片内容回复。）"


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(WELCOME)


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    await update.message.reply_text(HELP_TEXT)


async def cmd_clear(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message:
        return
    from src.telegram import history as tg_history

    chat_id = update.effective_chat.id if update.effective_chat else 0
    tg_history.clear(chat_id)
    await update.message.reply_text(CLEAR_DONE)


async def handle_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.text:
        return
    chat_id = update.effective_chat.id if update.effective_chat else 0
    user_text = (update.message.text or "").strip()
    if not user_text:
        return

    turn_input = UserTurnInput(text=user_text)
    try:
        reply = await tg_service.run_turn(chat_id, turn_input)
    except Exception as e:
        logger.exception("Telegram 单轮处理异常: %s", e)
        reply = "抱歉，我这边出错了，稍后再试吧。"
    await _send_reply(update, reply)


async def handle_voice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not update.message or not update.message.voice:
        return
    chat_id = update.effective_chat.id if update.effective_chat else 0

    try:
        tg_file = await context.bot.get_file(update.message.voice.file_id)
        buf = await tg_file.download_as_bytearray()
        audio_bytes = bytes(buf)
    except Exception as e:
        logger.warning("Telegram 语音下载失败: %s", e)
        await update.message.reply_text("语音下载失败，请重试。")
        return

    # STT 在同步函数中，放到线程执行避免阻塞
    loop = asyncio.get_event_loop()
    user_text = await loop.run_in_executor(
        None,
        lambda: hearing.speech_to_text(audio_bytes, "voice.ogg"),
    )
    user_text = (user_text or "").strip()
    if not user_text:
        await update.message.reply_text(VOICE_EMPTY)
        return

    turn_input = UserTurnInput(text=user_text)
    try:
        reply = await tg_service.run_turn(chat_id, turn_input)
    except Exception as e:
        logger.exception("Telegram 单轮处理异常: %s", e)
        reply = "抱歉，我这边出错了，稍后再试吧。"
    await _send_reply(update, reply)


async def handle_photo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """用户发图片即「眼睛」：下载后按 vision 配置压缩（vision_max_longer_side），再送入主脑。"""
    if not update.message or not update.message.photo:
        return
    chat_id = update.effective_chat.id if update.effective_chat else 0
    # 取最大尺寸的那张
    photo_sizes = list(update.message.photo)
    largest = max(photo_sizes, key=lambda p: p.width * p.height)
    caption = (update.message.caption or "").strip()

    try:
        tg_file = await context.bot.get_file(largest.file_id)
        buf = await tg_file.download_as_bytearray()
        raw_bytes = bytes(buf)
    except Exception as e:
        logger.warning("Telegram 图片下载失败: %s", e)
        await update.message.reply_text(PHOTO_FAIL)
        return

    try:
        from PIL import Image
        img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        # 与 Web 眼睛一致：按 config 压缩较长边并可选存 data/vision
        img = vision_module.prepare_image_for_turn(img, save=True)
    except Exception as e:
        logger.warning("Telegram 图片解析或压缩失败: %s", e)
        await update.message.reply_text(PHOTO_FAIL)
        return

    user_text = caption if caption else IMAGE_ONLY_PROMPT
    turn_input = UserTurnInput(text=user_text, images=[img])
    try:
        reply = await tg_service.run_turn(chat_id, turn_input)
    except Exception as e:
        logger.exception("Telegram 单轮处理异常: %s", e)
        reply = "抱歉，我这边出错了，稍后再试吧。"
    await _send_reply(update, reply)


def register_handlers(application: "object") -> None:
    """在 Application 上注册命令与消息处理器。"""
    from telegram.ext import CommandHandler, MessageHandler, filters

    application.add_handler(CommandHandler("start", cmd_start))
    application.add_handler(CommandHandler("help", cmd_help))
    application.add_handler(CommandHandler("clear", cmd_clear))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text))
    application.add_handler(MessageHandler(filters.VOICE, handle_voice))
    application.add_handler(MessageHandler(filters.PHOTO, handle_photo))
