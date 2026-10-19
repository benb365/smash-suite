"""Input restrictions of the first clipping product."""
from pathlib import Path
from modules.media.video import probe as probe_video

def probe(path: Path, name: str):
    import av
    info = probe_video(path, name)
    with av.open(str(path)) as container:
        if container.streams.video and container.streams.video[0].codec_context.name != "h264":
            raise ValueError("首版支持 H.264 编码的 MP4，请先转换视频编码。")
    if info.width > 1920 or info.height > 1080 or info.width < info.height:
        raise ValueError("首版支持不超过 1080p 的横屏录像。")
    return info
