"""
日志记录 — 格式化日志输出，便于 API 报错调试。
区分 [INFO], [DEBUG], [ERROR], [VISION], [AUDIO] 等标签，异步环境下不穿插错乱。
"""
import logging

try:
    import colorlog

    _handler = colorlog.StreamHandler()
    _handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s%(levelname)s [%(name)s] %(message)s",
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "red,bg_white",
            },
        )
    )
except ImportError:
    _handler = logging.StreamHandler()
    _handler.setFormatter(logging.Formatter("%(levelname)s [%(name)s] %(message)s"))


def get_logger(name: str) -> logging.Logger:
    """返回配置好的 logger 实例。"""
    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.addHandler(_handler)
        logger.setLevel(logging.INFO)
    return logger
