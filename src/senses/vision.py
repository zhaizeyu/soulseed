"""
眼睛 — 屏幕截取，直接输出图像对象，无 API 消耗。
基于 mss 或 Pillow.ImageGrab 抓取主屏/指定窗口；
可选图像差异对比 (Diff)，变化小时跳过抓取。返回 PIL.Image 或字节流。
"""
from typing import Any

# TODO: 实现 mss/Pillow 截屏 + 可选 Diff
def capture_screen() -> Any:
    """抓取当前屏幕，返回 PIL.Image 或兼容对象。"""
    try:
        from PIL import Image
        import mss
        with mss.mss() as sct:
            mon = sct.monitors[0]
            shot = sct.grab(mon)
            return Image.frombytes("RGB", shot.size, shot.bgra, "raw", "BGRX")
    except Exception:
        return None
