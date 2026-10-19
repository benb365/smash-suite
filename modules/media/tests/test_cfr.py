from modules.media.types import TimestampedFrame
from modules.media.video_input import iter_cfr_video_frames

def test_cfr_adapter_preserves_zero_based_source_timestamps_and_closes_capture(monkeypatch):
    import cv2

    class Capture:
        def __init__(self):
            self.images = iter(["frame0", "frame1", "frame2"])
            self.released = False

        def isOpened(self):
            return True

        def read(self):
            image = next(self.images, None)
            return image is not None, image

        def release(self):
            self.released = True

    capture = Capture()
    monkeypatch.setattr(cv2, "VideoCapture", lambda path: capture)
    assert list(iter_cfr_video_frames("seed.ts", fps=25, sample_stride=2)) == [
        TimestampedFrame(0, 0, "frame0"), TimestampedFrame(2, 80, "frame2")
    ]
    assert capture.released
