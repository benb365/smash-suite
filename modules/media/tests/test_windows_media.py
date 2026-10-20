"""Actual media regression checks for Unicode paths and encoder failures."""
import numpy as np
import pytest

from modules.media import video


@pytest.fixture
def unicode_video(tmp_path):
    av = pytest.importorskip("av")
    source = tmp_path / "中文目录" / "比赛片段.mp4"
    source.parent.mkdir()
    with av.open(str(source), "w") as container:
        stream = container.add_stream("libx264", rate=25)
        stream.width, stream.height, stream.pix_fmt = 64, 36, "yuv420p"
        for i in range(25):
            frame = av.VideoFrame.from_ndarray(np.full((36, 64, 3), i * 8, np.uint8), format="bgr24")
            container.mux(stream.encode(frame))
        container.mux(stream.encode())
    return source


def test_thumbnail_can_write_non_ascii_path(unicode_video):
    import cv2
    output = unicode_video.parent / "球场预览.jpg"
    video.thumbnail(unicode_video, output)
    assert output.is_file()
    image = cv2.imdecode(np.fromfile(output, dtype=np.uint8), cv2.IMREAD_COLOR)
    assert image.shape[:2] == (36, 64)


def test_encoder_error_with_unicode_source_keeps_actual_error(unicode_video, monkeypatch):
    info = video.probe(unicode_video, unicode_video.name)
    ffmpeg = video.ffmpeg_exe()

    def removed_source():
        # Reproduce disappearance between decoder inspection and FFmpeg open.
        # Only this fixture's file is removed; the encoder reports its UTF-8 name.
        unicode_video.unlink()
        return ffmpeg

    monkeypatch.setattr(video, "ffmpeg_exe", removed_source)
    with pytest.raises(RuntimeError, match="视频导出失败") as failure:
        video.render(unicode_video, unicode_video.parent / "output.mp4", [[0, 800]], info,
                     "balanced", lambda p: None)
    assert "比赛片段.mp4" in str(failure.value)
    assert not (unicode_video.parent / "rendering.mp4").exists()


def test_unicode_path_render_retains_size_and_decodable_frames(unicode_video):
    av = pytest.importorskip("av")
    info = video.probe(unicode_video, unicode_video.name)
    output = unicode_video.parent / "精彩回合.mp4"
    assert video.render(unicode_video, output, [[80, 880]], info, "balanced", lambda p: None) == 800
    with av.open(str(output)) as container:
        frames = list(container.decode(video=0))
    assert len(frames) == 20
    assert (frames[0].width, frames[0].height) == (64, 36)
    # A closed decoder leaves the file replaceable on Windows.
    moved = output.with_name("已保存.mp4")
    output.replace(moved)
    assert moved.is_file()
