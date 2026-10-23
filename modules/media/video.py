"""Probe source PTS and render one continuous original-sound MP4."""
from __future__ import annotations

import json
import math
import os
import shutil
import subprocess
import sys
from pathlib import Path

from .types import VideoInfo


def ffmpeg_exe() -> str:
    if getattr(sys, "frozen", False):
        path = Path(sys._MEIPASS) / "bin" / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
        if not path.is_file():
            raise RuntimeError("安装包缺少视频编码工具，请重新安装。")
        return str(path)
    configured = os.environ.get("SMASH_SUITE_FFMPEG")
    if configured:
        return configured
    found = shutil.which("ffmpeg")
    if found:
        return found
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def probe(path: Path, name: str) -> VideoInfo:
    import av
    try:
        with av.open(str(path)) as container:
            if not container.streams.video:
                raise ValueError("文件中没有视频画面。")
            stream = container.streams.video[0]
            first = next(container.decode(stream), None)
            if first is None or first.pts is None:
                raise ValueError("无法读取视频首帧时间。")
            first_ms = float(first.pts * first.time_base * 1000)
            duration_ms = (float(stream.duration * stream.time_base * 1000)
                           if stream.duration is not None else (container.duration or 0) / 1000)
            if not math.isfinite(duration_ms) or duration_ms <= 0:
                raise ValueError("无法读取视频时长。")
            return VideoInfo(name=name, duration_ms=duration_ms, width=first.width, height=first.height,
                             has_audio=bool(container.streams.audio), first_pts_ms=first_ms)
    except (av.error.FFmpegError, StopIteration) as exc:
        raise ValueError("无法读取 MP4，文件可能损坏或尚未录制完成。") from exc


def thumbnail(path: Path, destination: Path):
    import av
    import cv2
    with av.open(str(path)) as container:
        frame = next(container.decode(video=0))
        if not cv2.imwrite(str(destination), frame.to_ndarray(format="bgr24")):
            raise RuntimeError("无法生成球场选择画面。")


def selected_ranges(predictions, duration_ms: float, padding_ms: float = 0) -> list[list[float]]:
    ranges = []
    for row in predictions:
        start, end = float(row["start_ms"]), float(row["end_ms"])
        if not all(math.isfinite(v) for v in (start, end)) or start > end:
            raise ValueError("识别结果包含无效时间区间。")
        a, z = max(0, start - padding_ms), min(duration_ms, end + padding_ms)
        if z > a:
            ranges.append([a, z])
    merged = []
    for a, z in sorted(ranges):
        if merged and a <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], z)
        else:
            merged.append([a, z])
    return merged


def render(source: Path, output: Path, ranges: list[list[float]], info: VideoInfo, quality: str, progress,
           *, overlay_ass: Path | None = None):
    if not ranges:
        raise ValueError("没有识别到可保留的回合，未生成空视频。可检查拍摄类型或球场区域后重试。")
    # A single common origin preserves the actual audio/video offset. Never
    # independently apply PTS-STARTPTS to each track: that shifts delayed audio.
    origin = info.first_pts_ms / 1000
    import av
    with av.open(str(source)) as container:
        time_base = container.streams.video[0].time_base
    origin_pts = round(origin / time_base)
    count = len(ranges)
    seconds = [(a / 1000, z / 1000) for a, z in ranges]
    # Compare integer source ticks. Decimal seconds can round a 30fps boundary
    # upward, dropping its first frame while including the excluded end frame.
    # The sub-tick tolerance only removes floating-point arithmetic noise.
    ticks = [(math.ceil(a / time_base - 1e-6), math.ceil(z / time_base - 1e-6)) for a, z in seconds]
    selected = "+".join(f"gte(pts,{a})*lt(pts,{z})" for a, z in ticks)
    removed = f"{seconds[0][0] / time_base:.17g}" + "".join(
        f"+{(a - seconds[i - 1][1]) / time_base:.17g}*gte(PTS,{ticks[i][0]})"
        for i, (a, _) in enumerate(seconds) if i)
    # Keep real frame spacing and subtract only the removed source gaps.
    # Video concat guesses the last frame duration of each VFR segment and can
    # shift subsequent cuts. One select path also avoids buffering split video.
    filters = [f"[0:v]setpts=PTS-{origin_pts},select='{selected}',setpts='round(PTS-({removed}))'[video]"]
    video_label = "video"
    if overlay_ass is not None:
        ass_path = str(overlay_ass.resolve()).replace("\\", "\\\\").replace(":", "\\:").replace("'", "\\'")
        filters.append(f"[video]ass=filename='{ass_path}'[videoout]")
        video_label = "videoout"
    if info.has_audio:
        filters.append(f"[0:a:0]asetpts=PTS-({origin:.9f})/TB,aresample=async=1:first_pts=0,apad[abase]")
        filters.append(f"[abase]asplit={count}" + "".join(f"[a{i}]" for i in range(count)))
        for i, (a, z) in enumerate(seconds):
            filters.append(f"[a{i}]atrim=start={a:.9f}:end={z:.9f},asetpts=PTS-({a:.9f})/TB[ao{i}]")
        inputs = "".join(f"[ao{i}]" for i in range(count))
        filters.append(f"{inputs}concat=n={count}:v=0:a=1[audio]")
    script = output.with_suffix(".filters")
    script.write_text(";\n".join(filters), encoding="utf-8")
    temporary = output.with_name("rendering.mp4")
    command = [ffmpeg_exe(), "-hide_banner", "-nostdin", "-y", "-v", "error", "-copyts", "-i", str(source),
               "-filter_complex_script", str(script), "-map", f"[{video_label}]", "-c:v", "libx264",
               "-preset", "fast", "-crf", str({"high": 18, "balanced": 23, "small": 28}[quality]),
               "-pix_fmt", "yuv420p", "-fps_mode", "vfr", "-enc_time_base:v",
               f"{time_base.numerator}:{time_base.denominator}", "-bf", "0", "-threads", "4"]
    if info.has_audio:
        command += ["-map", "[audio]", "-c:a", "aac", "-b:a", "192k"]
    total_ms = sum(z - a for a, z in ranges)
    # Encode in presentation order so packet lookahead gives exact VFR sample
    # durations. Set the final sample's end explicitly instead of guessing a
    # nominal frame period, which can drop or shorten the final visible frame.
    duration_bsf = ("setts=pts=PTS:dts=DTS:duration=if(eq(NEXT_PTS\\,NOPTS)\\,"
                    f"{total_ms / 1000:.9f}/TB-PTS\\,NEXT_PTS-PTS)")
    command += ["-bsf:v", duration_bsf, "-movflags", "+faststart", "-progress", "pipe:1", "-nostats", str(temporary)]
    error_path = output.with_suffix(".ffmpeg.log")
    try:
        with error_path.open("w") as errors, subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors, text=True) as process:
            for line in process.stdout:
                if line.startswith("out_time_us="):
                    value = line.partition("=")[2].strip()
                    if value.isdigit():
                        progress(min(1, int(value) / 1000 / total_ms))
            if process.wait() != 0:
                details = error_path.read_text()[-2000:]
                raise RuntimeError(f"视频导出失败：{details}")
        # Decode the result before publishing it. A created file alone is not
        # evidence that the encoder finished or its output can be played.
        with av.open(str(temporary)) as container:
            if not container.streams.video or (info.has_audio and not container.streams.audio):
                raise RuntimeError("导出文件缺少预期音视频轨道。")
            frame = next(container.decode(video=0), None)
            if frame is None:
                raise RuntimeError("导出文件没有可播放的视频帧。")
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
    return total_ms
