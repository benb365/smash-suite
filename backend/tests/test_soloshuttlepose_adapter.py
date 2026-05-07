import json
from pathlib import Path

from app.vision.soloshuttlepose_adapter import (
    convert_soloshuttlepose_artifacts,
    parse_rally_intervals,
)


def test_parse_rally_intervals_from_text_artifact(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "rally.txt").write_text("rally intervals\n0:01 - 0:03\n", encoding="utf-8")

    result = parse_rally_intervals(raw_dir)

    assert result.status == "parsed"
    assert len(result.intervals) == 1
    assert result.intervals[0].start_ms == 1000.0
    assert result.intervals[0].end_ms == 3000.0


def test_parse_rally_intervals_from_soloshuttlepose_clip_name(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    clip_dir = raw_dir / "videos" / "test001"
    clip_dir.mkdir(parents=True)
    (clip_dir / "test001.json").write_text(
        json.dumps(
            {
                "video_name": "test001",
                "fps": 30.0,
                "height": 1080,
                "width": 1920,
                "total_frames": 300,
            }
        ),
        encoding="utf-8",
    )
    (clip_dir / "test001_30-89.mp4").write_bytes(b"")

    result = parse_rally_intervals(raw_dir)

    assert result.status == "parsed"
    assert result.parsed_sources == [str(clip_dir / "test001_30-89.mp4")]
    assert len(result.intervals) == 1
    assert result.intervals[0].start_ms == 1000.0
    assert result.intervals[0].end_ms == 3000.0


def test_convert_soloshuttlepose_artifacts_builds_scene_gate_json(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "segments.json").write_text(
        json.dumps(
            [
                {"category": "rally", "start_ms": 1000.0, "end_ms": 3000.0},
                {"category": "rally", "start_ms": 5000.0, "end_ms": 7000.0},
            ]
        ),
        encoding="utf-8",
    )

    scene_gate, manifest = convert_soloshuttlepose_artifacts(raw_dir, tmp_path / "video.mp4")

    assert manifest["parse_status"] == "parsed"
    assert scene_gate is not None
    assert [segment["category"] for segment in scene_gate["segments"]] == [
        "idle",
        "rally",
        "idle",
        "rally",
    ]


def test_convert_soloshuttlepose_artifacts_reports_needs_converter(tmp_path: Path) -> None:
    raw_dir = tmp_path / "raw"
    raw_dir.mkdir()
    (raw_dir / "unrecognized.txt").write_text("no useful intervals here", encoding="utf-8")

    scene_gate, manifest = convert_soloshuttlepose_artifacts(raw_dir, tmp_path / "video.mp4")

    assert scene_gate is None
    assert manifest["parse_status"] == "needs_converter"
