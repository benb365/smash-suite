from dataclasses import dataclass

from scan import interval_coverage, scan_frames


@dataclass
class Frame:
    frame_id: int
    timestamp_ms: float
    image: object


@dataclass
class Point:
    confidence: float


def test_scans_only_first_adjacent_trio_per_second_and_keeps_partial_tail():
    frames = [Frame(i, t, i) for i, t in enumerate((0, 40, 80, 120, 1000, 1040, 1080, 1120, 2000, 2040))]
    called = []

    def predict(images):
        called.append(images)
        return [Point(.49), Point(.5), Point(.51)]

    groups, tail = scan_frames(iter(frames), predict)

    assert called == [[0, 1, 2], [4, 5, 6]]
    assert [(row["source_second"], row["frame_ids"], row["timestamps_ms"])
            for row in groups] == [(0, [0, 1, 2], [0, 40, 80]), (1, [4, 5, 6], [1000, 1040, 1080])]
    assert [point["positive"] for point in groups[0]["frames"]] == [False, True, True]
    assert tail == [[{"frame_id": 8, "timestamp_ms": 2000}, {"frame_id": 9, "timestamp_ms": 2040}]]


def test_coverage_uses_per_frame_half_open_time_and_inclusive_threshold():
    samples = [
        {"timestamp_ms": 99, "confidence": .9},
        {"timestamp_ms": 100, "confidence": .5},
        {"timestamp_ms": 199, "confidence": .2},
        {"timestamp_ms": 200, "confidence": .99},
    ]

    raw = interval_coverage(samples, [{"start_ms": 100, "end_ms": 200}, {"start_ms": 101, "end_ms": 150},
                                      {"start_ms": 150, "end_ms": 200}, {"start_ms": 101, "end_ms": 200}])
    export = interval_coverage(samples, [[101, 201]])

    assert raw[0] == {"index": 0, "start_ms": 100, "end_ms": 200, "sample_count": 2,
                      "hit_count": 1, "hit": True, "hit_timestamps_ms": [100],
                      "max_confidence": .5, "max_timestamp_ms": 100}
    assert raw[1]["sample_count"] == 0 and raw[1]["hit"] is False and raw[1]["max_confidence"] is None
    assert raw[2]["hit"] is False and raw[2]["max_confidence"] == .2 and raw[2]["hit_timestamps_ms"] == []
    assert raw[3]["hit"] is False and raw[3]["max_confidence"] == .2
    assert export[0]["hit"] is True and export[0]["hit_timestamps_ms"] == [200]
    assert raw[3]["hit"] is False and export[0]["hit"] is True
