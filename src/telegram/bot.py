"""
构建 PTB Application，注册 handlers，提供 run_polling。
Token 与开关从 config / 环境变量读取。
"""
from telegram.ext import Application

from src.core.config_loader import get_config
from src.core.logger import get_logger
from src.telegram.handlers import register_handlers

logger = get_logger(__name__)


def get_bot_token() -> str | None:
    """从 config 取 TELEGRAM_BOT_TOKEN（.env 已由 config_loader 加载）。"""
    cfg = get_config()
    token = (cfg.get("TELEGRAM_BOT_TOKEN") or "").strip()
    return token or None


def is_telegram_enabled() -> bool:
    cfg = get_config()
    v = cfg.get("telegram_enabled")
    if v is None:
        return False
    if isinstance(v, bool):
        return v
    if isinstance(v, str):
        return v.lower() not in ("false", "0", "no", "off")
    return bool(v)


def build_application() -> Application:
    token = get_bot_token()
    if not token:
        raise RuntimeError("未配置 TELEGRAM_BOT_TOKEN（config 或环境变量 .env）")
    app = Application.builder().token(token).build()
    register_handlers(app)
    return app


def run_polling() -> None:
    if not is_telegram_enabled():
        logger.warning("telegram_enabled 未开启，请在 config.yaml 中设置 telegram_enabled: true")
    app = build_application()
    logger.info("Telegram Bot 启动 polling…")
    app.run_polling()
