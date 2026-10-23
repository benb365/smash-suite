"""Stream-copy MP4 edit lists must not be mistaken for truncated decoding."""
import subprocess

import numpy as np
import pytest

from modules.media.video import ffmpeg_exe
from modules.media.video_input import FileFrameSource, _verified_edit_list_frames


@pytest.fixture
def stream_copy_clip(tmp_path):
    av = pytest.importorskip("av")
    original = tmp_path / "original.mp4"
    with av.open(str(original), "w") as container:
        stream = container.add_stream("libx264", rate=25)
        stream.width, stream.height, stream.pix_fmt = 64, 36, "yuv420p"
        stream.options = {"g": "100", "keyint_min": "100", "sc_threshold": "0", "bf": "2"}
        for i in range(125):
            frame = av.VideoFrame.from_ndarray(np.full((36, 64, 3), i % 240, np.uint8), format="bgr24")
            container.mux(stream.encode(frame))
        container.mux(stream.encode())
    clip = tmp_path / "stream-copy.mp4"
    subprocess.run([ffmpeg_exe(), "-hide_banner", "-nostdin", "-v", "error", "-y",
                    "-ss", "1.2", "-i", str(original), "-t", "2", "-c", "copy",
                    "-movflags", "+faststart", str(clip)], check=True, capture_output=True)
    return clip


def test_native_stream_copy_edit_list_accepts_only_presented_frames(stream_copy_clip):
    import av
    with av.open(str(stream_copy_clip)) as container:
        declared = container.streams.video[0].frames
        reference = [float(frame.pts * frame.time_base * 1000) for frame in container.decode(video=0)]
    assert declared > len(reference), "Fixture must exercise a real edit-list omission"
    proof = _verified_edit_list_frames(stream_copy_clip, declared, len(reference))
    assert proof is not None
    assert proof["edit_list_omitted_samples"] == declared - len(reference)
    with FileFrameSource(stream_copy_clip) as source:
        delivered = [frame.timestamp_ms for frame in source]
    assert delivered == pytest.approx([pts - reference[0] for pts in reference])
    assert source.stats["frames_delivered"] == len(reference)
    assert source.stats["edit_list_verification"] == proof


def test_edit_list_validation_counts_decoded_frames_before_fps_selection(stream_copy_clip):
    import av
    with av.open(str(stream_copy_clip)) as container:
        reference = [frame for frame in container.decode(video=0)]
    with FileFrameSource(stream_copy_clip, max_fps=10) as source:
        delivered = [(frame.frame_id, frame.timestamp_ms) for frame in source]
    assert 0 < len(delivered) < len(reference)
    assert source.stats["frames_decoded"] == len(reference)
    assert source.stats["expected_frames"] == len(reference)
    assert source.stats["frames_selected"] == source.stats["frames_delivered"] == len(delivered)
    assert source.stats["frames_skipped"] == len(reference) - len(delivered)
    assert source.stats["edit_list_verification"]["presented_frames"] == len(reference)
    assert delivered[0][0] == 0
    assert all(a[0] < b[0] and a[1] < b[1] for a, b in zip(delivered, delivered[1:]))


@pytest.mark.parametrize("max_fps", [None, 10])
def test_truncated_stream_copy_remains_a_failure(stream_copy_clip, max_fps):
    # The fast-start sample table survives, while required media samples do not.
    data = stream_copy_clip.read_bytes()
    stream_copy_clip.write_bytes(data[:-max(400, len(data) // 8)])
    with pytest.raises((RuntimeError, ValueError, __import__("av").error.FFmpegError)):
        with FileFrameSource(stream_copy_clip, max_fps=max_fps) as source:
            list(source)
