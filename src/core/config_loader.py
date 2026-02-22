"""
配置管理 — 单例模式，统一加载 .env 和 config.yaml。
将业务配置与机密凭证合并为全局可访问的配置对象。
"""
from pathlib import Path
from typing import Any

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
        config["GEMINI_API_KEY"] = (os.getenv("GEMINI_API_KEY") or "").strip()
        config["OPENAI_API_KEY"] = (os.getenv("OPENAI_API_KEY") or "").strip()
        config["VTS_PORT"] = int(os.getenv("VTS_PORT", "8001"))
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
