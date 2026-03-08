"""
独立入口：python -m src.telegram
仅启动 Telegram Bot（polling），与 CLI / Web 并列。
"""
import warnings
warnings.filterwarnings("ignore", category=DeprecationWarning, message=".*AiohttpClientSession.*")

from src.telegram.bot import run_polling

if __name__ == "__main__":
    run_polling()
