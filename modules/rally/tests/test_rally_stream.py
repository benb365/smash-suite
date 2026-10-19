import math

import pytest

from modules.media.types import TimestampedFrame
from modules.rally.types import RallyInterval
from modules.rally.rally_stream import RallyStream, replay_frames


class RecordingSegmenter:
    def __init__(self):
        self.seen = []

    def process(self, frame):
        self.seen.append(frame.frame_id)
        if frame.frame_id == 2:
            return [RallyInterval(1, 10, 20, frame.timestamp_ms)]
        return []

    def flush(self):
        raise AssertionError("Replay must not force an unfinished rally to end at EOF")


def test_replay_is_lazy_and_keeps_emission_time_without_eof_flush():
    segmenter = RecordingSegmenter()

    def frames():
        for index, timestamp in enumerate((0, 10, 30)):
            assert segmenter.seen == list(range(index))
            yield TimestampedFrame(index, timestamp, object())

    result = replay_frames(frames(), segmenter, source_duration_ms=40)
    assert result["predictions"] == [RallyInterval(1, 10, 20, 30)]
    assert result["frames_processed"] == 3
    assert result["realtime_factor"] > 0


@pytest.mark.parametrize("frame", [TimestampedFrame(1, 10, None), TimestampedFrame(2, 10, None), TimestampedFrame(2, 9, None)])
def test_rejects_duplicate_ids_duplicate_times_and_time_regression_before_inference(frame):
    segmenter = RecordingSegmenter()
    stream = RallyStream(segmenter)
    stream.process(TimestampedFrame(1, 10, None))
    with pytest.raises(ValueError, match="strictly increasing"):
        stream.process(frame)
    assert segmenter.seen == [1]


@pytest.mark.parametrize("value", [math.nan, math.inf, -math.inf])
def test_rejects_nonfinite_timestamps(value):
    with pytest.raises(ValueError, match="finite"):
        RallyStream(RecordingSegmenter()).process(TimestampedFrame(0, value, None))


def test_rejects_duplicate_rally_outputs_and_wrong_source_emission_time():
    class DuplicateSegmenter:
        def process(self, frame):
            return [RallyInterval(1, 0, 1, frame.timestamp_ms)]

    stream = RallyStream(DuplicateSegmenter())
    stream.process(TimestampedFrame(0, 2, None))
    with pytest.raises(ValueError, match="only be emitted once"):
        stream.process(TimestampedFrame(1, 3, None))

    class FutureSegmenter:
        def process(self, frame):
            return [RallyInterval(1, 0, 1, frame.timestamp_ms + 1)]

    with pytest.raises(ValueError, match="current source frame"):
        RallyStream(FutureSegmenter()).process(TimestampedFrame(0, 2, None))


def test_rejects_invalid_interval_and_invalid_source_duration():
    with pytest.raises(ValueError, match="integer"):
        RallyInterval("1", 0, 1, 2)
    with pytest.raises(ValueError, match="integer"):
        RallyStream(RecordingSegmenter()).process(TimestampedFrame(math.nan, 0, None))
    with pytest.raises(ValueError, match="start_ms <="):
        RallyInterval(1, 2, 1, 3)
    with pytest.raises(ValueError, match="finite"):
        RallyInterval(1, 0, 1, math.inf)
    with pytest.raises(ValueError, match="nonnegative"):
        replay_frames([], RecordingSegmenter(), source_duration_ms=-1)


