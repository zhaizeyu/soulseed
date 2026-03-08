"""
眼睛 — 屏幕截取，供主脑多模态输入。
基于 mss 抓取主屏；按较长边缩放以控制 token；可选存盘到 data/vision。
心跳检测：每 N 秒截图与上一张做对比，差异超过阈值则视为「数字生命感兴趣的变动」，供调度器触发主动说话。
"""
from datetime import datetime
from pathlib import Path
from typing import Any

from src.core.config_loader import get_config
from src.core.logger import get_logger

logger = get_logger(__name__)

# 心跳检测：上一帧缩略图（小图用于对比），None 表示尚未有上一帧
_last_heartbeat_thumb: Any = None

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


def prepare_image_for_turn(image: Any, *, save: bool = False) -> Any:
    """
    按「眼睛」配置处理图片：较长边缩放到 vision_max_longer_side，与 get_screen_for_turn 一致。
    供 Telegram 发图等作为眼睛输入时复用，控制 token。若 save=True，按 vision_save_* 写入 data/vision。
    返回处理后的 PIL.Image。
    """
    if image is None:
        return None
    cfg = get_config()
    try:
        max_side = int(cfg.get("vision_max_longer_side") or 0)
    except (TypeError, ValueError):
        max_side = 0
    if max_side > 0:
        image = _resize_longer_side(image, max_side)
    if save:
        _save_screenshot(image, cfg)
    return image


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
    img = prepare_image_for_turn(img, save=True)
    return img


# 心跳检测用缩略图尺寸（仅用于差异对比，省内存）
_HEARTBEAT_THUMB_SIZE = (64, 64)


def _image_to_thumb(image: Any) -> Any:
    """将 PIL 图转为固定尺寸灰度缩略图，用于心跳对比。"""
    if image is None:
        return None
    try:
        from PIL import Image
        gray = image.convert("L")
        return gray.resize(_HEARTBEAT_THUMB_SIZE, Image.Resampling.LANCZOS)
    except Exception:
        return None


def _diff_ratio(thumb_a: Any, thumb_b: Any) -> float:
    """
    计算两幅缩略图的像素差异比例 (0~1)。
    使用平均绝对差除以 255；0 表示完全相同，越大变化越明显。
    """
    if thumb_a is None or thumb_b is None:
        return 1.0
    try:
        from PIL import ImageChops
        diff = ImageChops.difference(thumb_a, thumb_b)
        data = list(diff.getdata())
        if not data:
            return 0.0
        return sum(data) / len(data) / 255.0
    except Exception:
        return 1.0


def check_heartbeat() -> tuple[bool, Any]:
    """
    心跳检测：截取当前屏幕，与上一帧缩略图对比。
    若差异超过配置阈值，视为「数字生命感兴趣的变动」，返回 (True, 当前帧大图) 供本回合主脑使用；
    否则返回 (False, None)。
    首帧或未开启心跳时返回 (False, None)，并更新上一帧供下次对比。
    """
    global _last_heartbeat_thumb
    cfg = get_config()
    if not cfg.get("vision_enabled", True):
        return False, None
    if not cfg.get("vision_heartbeat_enabled", False):
        return False, None
    img = capture_screen()
    if img is None:
        return False, None
    try:
        max_side = int(cfg.get("vision_max_longer_side") or 0)
    except (TypeError, ValueError):
        max_side = 0
    if max_side > 0:
        img = _resize_longer_side(img, max_side)
    thumb = _image_to_thumb(img)
    if thumb is None:
        return False, None
    threshold = 0.03
    try:
        t = float(cfg.get("vision_heartbeat_diff_threshold", 0.03))
        threshold = max(0.0, min(1.0, t))
    except (TypeError, ValueError):
        pass
    triggered = False
    if _last_heartbeat_thumb is not None:
        ratio = _diff_ratio(_last_heartbeat_thumb, thumb)
        if ratio >= threshold:
            triggered = True
            logger.info("[VISION] 心跳检测到画面变化 (diff=%.4f >= %.4f)，触发主动说话", ratio, threshold)
        else:
            logger.info("[VISION] 心跳检测: diff=%.4f < 阈值%.4f，未触发", ratio, threshold)
    else:
        logger.info("[VISION] 心跳检测: 首帧已保存为基准，下次对比将在 %s 秒后", cfg.get("vision_heartbeat_interval_sec", 30))
    _last_heartbeat_thumb = thumb
    if triggered:
        _save_screenshot(img, cfg)
        return True, img
    return False, None
