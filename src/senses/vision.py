"""
眼睛 — 屏幕截取，供主脑多模态输入。
基于 mss 抓取主屏；按较长边缩放以控制 token；可选存盘到 data/vision。
"""
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config_loader import get_config
from src.core.logger import get_logger

logger = get_logger(__name__)

# 项目根，用于解析相对路径
_PROJECT_ROOT = Path(__file__).resolve().parents[2]


def capture_screen() -> Any:
    """抓取当前主屏，返回 PIL.Image 或 None。"""
    try:
        from PIL import Image
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[0]
            shot = sct.grab(mon)
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    except Exception:
        return None


def _resize_longer_side(image: Any, max_longer: int) -> Any:
    """将图像较长边缩放到 max_longer，保持比例。"""
    if image is None or max_longer <= 0:
        return image
    try:
        from PIL import Image
        w, h = image.size
        longer = max(w, h)
        if longer <= max_longer:
            return image
        scale = max_longer / longer
        nw, nh = int(w * scale), int(h * scale)
        return image.resize((nw, nh), Image.Resampling.LANCZOS)
    except Exception:
        return image


def _save_screenshot(image: Any, cfg: dict) -> None:
    """将截图写入 data/vision，按配置格式与质量。"""
    if image is None:
        return
    if not cfg.get("vision_save_enabled", True):
        return
    save_dir = cfg.get("vision_save_dir") or "data/vision"
    save_path = _PROJECT_ROOT / save_dir
    try:
        save_path.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        logger.warning("创建截图目录失败 %s: %s", save_path, e)
        return
    fmt = (cfg.get("vision_save_format") or "jpg").strip().lower()
    if fmt not in ("jpg", "jpeg", "png"):
        fmt = "jpg"
    ext = "png" if fmt == "png" else "jpg"
    try:
        quality = int(cfg.get("vision_jpeg_quality") or 85)
        quality = max(1, min(100, quality))
    except (TypeError, ValueError):
        quality = 85
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    file_path = save_path / f"screenshot_{stamp}.{ext}"
    try:
        if ext == "jpg":
            image.save(file_path, "JPEG", quality=quality, optimize=True)
        else:
            image.save(file_path, "PNG", optimize=True)
        logger.debug("截图已保存: %s", file_path)
    except Exception as e:
        logger.warning("保存截图失败 %s: %s", file_path, e)


def get_screen_for_turn() -> Any:
    """
    根据 config 抓取并处理当前屏幕，供本回合主脑使用。
    会先缩放（vision_max_longer_side），再按配置写入 data/vision，最后返回 PIL.Image。
    若 vision_enabled 为 false 或截屏失败则返回 None。
    """
    cfg = get_config()
    if not cfg.get("vision_enabled", True):
        return None
    img = capture_screen()
    if img is None:
        return None
    try:
        max_side = int(cfg.get("vision_max_longer_side") or 0)
    except (TypeError, ValueError):
        max_side = 0
    if max_side > 0:
        img = _resize_longer_side(img, max_side)
    _save_screenshot(img, cfg)
    return img
