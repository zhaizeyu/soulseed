"""
配置管理 — 单例模式，统一加载 .env 和 config.yaml。
将业务配置与机密凭证合并为全局可访问的配置对象。
"""
from pathlib import Path
from typing import Any


def _env_str(name: str) -> str | None:
    """读取环境变量（去首尾空白）；未设置或为空返回 None。"""
    import os

    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value or None


# 占位：实际实现中加载 dotenv + yaml，返回合并后的配置对象
def load_config() -> dict[str, Any]:
    """加载并返回全局配置。"""
    root = Path(__file__).resolve().parents[2]
    config_path = root / "config.yaml"
    config: dict[str, Any] = {}
    if config_path.exists():
        try:
            import yaml
            with open(config_path, "r", encoding="utf-8") as f:
                config = yaml.safe_load(f) or {}
        except Exception:
            pass
    try:
        from dotenv import load_dotenv
        import os
        load_dotenv(root / ".env")

        # 统一从 .env 覆盖模型与网关相关配置（后端启动即生效）
        for key in (
            "LITELLM_API_KEY",
            "OPENAI_BASE_URL",
            "CHAT_MODEL",
            "VISION_TO_TEXT_MODEL",
            "DISABLE_SENSITIVE_CHECK",
            "EMBEDDING_MODEL",
            "EMBEDDING_DIMENSION",
            "IMAGE_GENERATION_MODEL",
            "LANGFUSE_PUBLIC_KEY",
            "LANGFUSE_SECRET_KEY",
            "LANGFUSE_BASE_URL",
            "LANGFUSE_PROMPT_MAP_KEY",
            "LANGFUSE_SYSTEM_PROMPT_ENABLED",
            "APP_TIMEZONE",
            "TELEGRAM_BOT_TOKEN",
        ):
            value = _env_str(key)
            if value is not None:
                config[key] = value

        # 端口类配置允许从 .env 覆盖
        vts_port = _env_str("VTS_PORT")
        if vts_port is not None:
            try:
                config["VTS_PORT"] = int(vts_port)
            except ValueError:
                pass
        elif "VTS_PORT" not in config:
            config["VTS_PORT"] = 8001

        # LiteLLM / Langfuse SDK 常用环境变量
        if config.get("OPENAI_BASE_URL"):
            os.environ["OPENAI_BASE_URL"] = str(config["OPENAI_BASE_URL"])
        if config.get("LANGFUSE_PUBLIC_KEY"):
            os.environ["LANGFUSE_PUBLIC_KEY"] = str(config["LANGFUSE_PUBLIC_KEY"])
        if config.get("LANGFUSE_SECRET_KEY"):
            os.environ["LANGFUSE_SECRET_KEY"] = str(config["LANGFUSE_SECRET_KEY"])
        langfuse_host = str(config.get("LANGFUSE_BASE_URL") or _env_str("LANGFUSE_HOST") or "")
        if langfuse_host:
            config["LANGFUSE_HOST"] = langfuse_host
            os.environ["LANGFUSE_HOST"] = langfuse_host
    except ImportError:
        pass
    return config


_config: dict[str, Any] | None = None


def get_config() -> dict[str, Any]:
    """单例获取配置。"""
    global _config
    if _config is None:
        _config = load_config()
    return _config
