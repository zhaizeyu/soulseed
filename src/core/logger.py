"""
日志记录 — 格式化日志输出，便于 API 报错调试。
同时输出到控制台与日志文件；路径由 config 的 log_dir / log_file 决定。
"""
import logging
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[2]
_LOG_FILE: Path | None = None  # 首次 _ensure_file_handler 时从 config 解析

try:
    import colorlog
    _console_formatter = colorlog.ColoredFormatter(
        "%(log_color)s%(levelname)s [%(name)s] %(message)s",
        log_colors={
            "DEBUG": "cyan",
            "INFO": "green",
            "WARNING": "yellow",
            "ERROR": "red",
            "CRITICAL": "red,bg_white",
        },
    )
    _console_handler = colorlog.StreamHandler()
    _console_handler.setFormatter(_console_formatter)
except ImportError:
    _console_handler = logging.StreamHandler()
    _console_handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))

_file_handler: logging.FileHandler | None = None


def _get_log_path() -> Path:
    """从 config 解析日志文件路径（log_dir + log_file），未配置则用默认。"""
    global _LOG_FILE
    if _LOG_FILE is not None:
        return _LOG_FILE
    try:
        from src.core.config_loader import get_config
        cfg = get_config()
        log_dir = (cfg.get("log_dir") or "logs").strip()
        log_file = (cfg.get("log_file") or "vedalai.log").strip()
        p_dir = Path(log_dir)
        if p_dir.is_absolute():
            _LOG_FILE = p_dir / log_file
        else:
            _LOG_FILE = _PROJECT_ROOT / log_dir / log_file
    except Exception:
        _LOG_FILE = _PROJECT_ROOT / "logs" / "vedalai.log"
    return _LOG_FILE


def _ensure_file_handler() -> logging.FileHandler:
    global _file_handler
    if _file_handler is not None:
        return _file_handler
    log_path = _get_log_path()
    log_path.parent.mkdir(parents=True, exist_ok=True)
    _file_handler = logging.FileHandler(log_path, encoding="utf-8")
    _file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s"))
    return _file_handler


def get_logger(name: str) -> logging.Logger:
    """返回配置好的 logger 实例；同时输出到控制台与日志文件（路径见 config log_dir/log_file）。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_console_handler)
        try:
            logger.addHandler(_ensure_file_handler())
        except OSError:
            pass
        logger.setLevel(logging.INFO)
    return logger


def get_log_path() -> Path:
    """返回当前日志文件路径，便于在报错信息中提示用户。"""
    return _get_log_path()
