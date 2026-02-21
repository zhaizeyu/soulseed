"""
播放器 — 后台常驻音频消费队列；播放时向 body 广播状态与音量；
播放完毕清理 assets/temp/ 缓存；对外暴露 interrupt() 实现瞬间闭嘴。
"""
# TODO: 异步队列、音频播放、RMS 送 body、interrupt()
def interrupt() -> None:
    """清空播放队列并停止当前播放。"""
    pass
