"""
物理表征 — VTube Studio 协议封装。基于 pyvts 建立 WebSocket；
接收 player 的音频 RMS 映射 MouthOpen 实现唇形同步；
正则匹配主脑输出情感标签 (如 *laughs*) 触发表情热键。
"""
# TODO: pyvts 连接、Lip-sync、表情热键
def send_mouth_open(value: float) -> None:
    """向 VTS 发送口型开合度。"""
    pass
