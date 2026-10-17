from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Optional

from app.model_utils import model_to_dict
from app.models import SceneGateResult, SceneSegment
from app.vision.scene_eval import Interval, format_ms, merge_intervals


RALLY_KEYWORDS = ("rally", "game", "play", "valid")
START_KEYS = ("start_ms", "start_time_ms", "start_frame_ms", "start", "begin", "start_time")
END_KEYS = ("end_ms", "end_time_ms", "end_frame_ms", "end", "finish", "end_time")
VIDEO_SUFFIXES = {".mp4"}
SOLO_CLIP_PATTERN = re.compile(r"^(?P<video_name>.+)_(?P<start_frame>\d+)-(?P<end_frame>\d+)$")


@dataclass(frozen=True)
class SoloArtifact:
    path: str
    kind: str
    size_bytes: int


@dataclass(frozen=True)
class SoloParseResult:
    status: str
    intervals: List[Interval]
    parsed_sources: List[str]
    warnings: List[str]


def scan_artifacts(raw_result_dir: Path) -> list[dict[str, Any]]:
    if not raw_result_dir.exists():
        return []

    artifacts = []
    for path in sorted(item for item in raw_result_dir.rglob("*") if item.is_file()):
        artifacts.append(
            {
                "path": str(path),
                "kind": path.suffix.lower().lstrip(".") or "unknown",
                "size_bytes": path.stat().st_size,
            }
        )
    return artifacts


def convert_soloshuttlepose_artifacts(
    raw_result_dir: Path,
    video_path: Path,
) -> tuple[Optional[dict[str, Any]], dict[str, Any]]:
    artifacts = scan_artifacts(raw_result_dir)
    parse_result = parse_rally_intervals(raw_result_dir, default_fps=_video_fps(video_path))
    manifest: dict[str, Any] = {
        "source": "SoloShuttlePose",
        "raw_result_dir": str(raw_result_dir),
        "video_path": str(video_path),
        "artifact_count": len(artifacts),
        "artifacts": artifacts,
        "parse_status": parse_result.status,
        "parsed_sources": parse_result.parsed_sources,
        "warnings": parse_result.warnings,
    }

    if not parse_result.intervals:
        manifest["next_step"] = (
            "Inspect raw artifacts and add a converter for the SoloShuttlePose output format."
        )
        return None, manifest

    scene_gate = build_scene_gate_result(
        video_path=video_path,
        intervals=parse_result.intervals,
        config={
            "source": "SoloShuttlePose",
            "raw_result_dir": str(raw_result_dir),
            "parsed_sources": parse_result.parsed_sources,
            "parse_status": parse_result.status,
        },
    )
    return model_to_dict(scene_gate), manifest


def parse_rally_intervals(
    raw_result_dir: Path,
    default_fps: Optional[float] = None,
) -> SoloParseResult:
    intervals: List[Interval] = []
    parsed_sources: List[str] = []
    warnings: List[str] = []

    if not raw_result_dir.exists():
        return SoloParseResult(
            status="missing_raw_result_dir",
            intervals=[],
            parsed_sources=[],
            warnings=[f"Raw result directory does not exist: {raw_result_dir}"],
        )

    fps_by_video = _read_video_metadata_fps(raw_result_dir, warnings)
    for path in sorted(item for item in raw_result_dir.rglob("*") if item.is_file()):
        if path.suffix.lower() == ".json":
            parsed = _parse_json_intervals(path, warnings)
        elif path.suffix.lower() == ".csv":
            parsed = _parse_csv_intervals(path, warnings)
        elif path.suffix.lower() in {".txt", ".log", ".md"}:
            parsed = _parse_text_intervals(path, warnings)
        elif path.suffix.lower() in VIDEO_SUFFIXES:
            parsed = _parse_video_clip_interval(path, fps_by_video, default_fps, warnings)
        else:
            parsed = []

        if parsed:
            intervals.extend(parsed)
            parsed_sources.append(str(path))

    intervals = merge_intervals(intervals)
    status = "parsed" if intervals else "needs_converter"
    return SoloParseResult(
        status=status,
        intervals=intervals,
        parsed_sources=parsed_sources,
        warnings=warnings,
    )


def build_scene_gate_result(
    video_path: Path,
    intervals: Iterable[Interval],
    config: dict[str, Any],
) -> SceneGateResult:
    merged = merge_intervals(intervals)
    duration_ms = _video_duration_ms(video_path, merged)
    segments: List[SceneSegment] = []
    cursor_ms = 0.0
    frame_rate = _video_fps(video_path)

    for interval in merged:
        start_ms = max(0.0, interval.start_ms)
        end_ms = min(duration_ms, interval.end_ms) if duration_ms else interval.end_ms
        if start_ms > cursor_ms:
            segments.append(
                _segment("idle", cursor_ms, start_ms, "soloshuttlepose_gap", frame_rate)
            )
        if end_ms > start_ms:
            segments.append(
                _segment("rally", start_ms, end_ms, "soloshuttlepose_rally", frame_rate)
            )
        cursor_ms = max(cursor_ms, end_ms)

    if duration_ms > cursor_ms:
        segments.append(_segment("idle", cursor_ms, duration_ms, "soloshuttlepose_gap", frame_rate))

    retained_ms = sum(segment.end_ms - segment.start_ms for segment in segments if segment.category == "rally")
    return SceneGateResult(
        video_path=str(video_path),
        fps=round(frame_rate, 3),
        frame_count=_video_frame_count(video_path),
        duration_ms=round(duration_ms, 3),
        analyzed_frame_count=0,
        sample_stride=1,
        retained_ms=round(retained_ms, 3),
        retained_ratio=round(retained_ms / duration_ms, 4) if duration_ms else 0.0,
        smash_candidate_ms=0.0,
        smash_candidate_ratio=0.0,
        category_durations_ms={
            "rally": round(retained_ms, 3),
            "idle": round(max(0.0, duration_ms - retained_ms), 3),
        },
        segments=segments,
        smash_candidates=[],
        config=config,
    )


def build_needs_converter_report(manifest: dict[str, Any]) -> str:
    lines = [
        "# SoloShuttlePose spike report",
        "",
        f"- Status: `{manifest.get('parse_status', 'unknown')}`",
        f"- Raw result dir: `{manifest.get('raw_result_dir')}`",
        f"- Artifact count: `{manifest.get('artifact_count', 0)}`",
        "",
        "## Parsed Sources",
        "",
        *_format_list(manifest.get("parsed_sources", [])),
        "",
        "## Warnings",
        "",
        *_format_list(manifest.get("warnings", [])),
        "",
        "## Next Step",
        "",
        manifest.get(
            "next_step",
            "Run SoloShuttlePose, inspect raw artifacts, then add a converter if needed.",
        ),
    ]
    return "\n".join(lines) + "\n"


def _parse_json_intervals(path: Path, warnings: list[str]) -> list[Interval]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Could not parse JSON {path}: {exc}")
        return []
    return list(_intervals_from_json_value(data))


def _parse_csv_intervals(path: Path, warnings: list[str]) -> list[Interval]:
    try:
        with path.open(newline="", encoding="utf-8") as csv_file:
            rows = list(csv.DictReader(csv_file))
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Could not parse CSV {path}: {exc}")
        return []

    intervals = []
    for row in rows:
        if not _row_is_rally_like(row):
            continue
        interval = _interval_from_mapping(row)
        if interval is not None:
            intervals.append(interval)
    return intervals


def _parse_text_intervals(path: Path, warnings: list[str]) -> list[Interval]:
    try:
        text = path.read_text(encoding="utf-8", errors="ignore")
    except Exception as exc:  # noqa: BLE001
        warnings.append(f"Could not read text {path}: {exc}")
        return []

    intervals = []
    for match in re.finditer(
        r"(?P<start>\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)\s*[-,~]\s*"
        r"(?P<end>\d{1,2}:\d{2}(?::\d{2})?(?:\.\d+)?)",
        text,
    ):
        start_ms = _parse_time_value(match.group("start"))
        end_ms = _parse_time_value(match.group("end"))
        if start_ms is not None and end_ms is not None and end_ms > start_ms:
            intervals.append(Interval(start_ms=start_ms, end_ms=end_ms))
    return intervals


def _read_video_metadata_fps(raw_result_dir: Path, warnings: list[str]) -> dict[str, float]:
    fps_by_video: dict[str, float] = {}
    for path in sorted(item for item in raw_result_dir.rglob("*.json") if item.is_file()):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        if not isinstance(data, dict):
            continue

        video_name = data.get("video_name")
        fps = _coerce_positive_float(data.get("fps"))
        if isinstance(video_name, str) and fps is not None:
            fps_by_video[video_name] = fps

    if not fps_by_video:
        warnings.append("No SoloShuttlePose video metadata JSON with fps was found.")
    return fps_by_video


def _parse_video_clip_interval(
    path: Path,
    fps_by_video: dict[str, float],
    default_fps: Optional[float],
    warnings: list[str],
) -> list[Interval]:
    match = SOLO_CLIP_PATTERN.match(path.stem)
    if not match:
        return []

    video_name = match.group("video_name")
    start_frame = int(match.group("start_frame"))
    end_frame = int(match.group("end_frame"))
    if end_frame < start_frame:
        warnings.append(f"Invalid SoloShuttlePose clip frame range in {path}.")
        return []

    fps = fps_by_video.get(video_name) or _coerce_positive_float(default_fps)
    if fps is None:
        warnings.append(f"Could not convert SoloShuttlePose clip frames without fps: {path}")
        return []

    return [
        Interval(
            start_ms=start_frame / fps * 1000.0,
            end_ms=(end_frame + 1) / fps * 1000.0,
        )
    ]


def _intervals_from_json_value(value: Any) -> Iterable[Interval]:
    if isinstance(value, list):
        for item in value:
            yield from _intervals_from_json_value(item)
        return

    if not isinstance(value, dict):
        return

    if _row_is_rally_like(value):
        interval = _interval_from_mapping(value)
        if interval is not None:
            yield interval

    for nested in value.values():
        if isinstance(nested, (dict, list)):
            yield from _intervals_from_json_value(nested)


def _row_is_rally_like(row: dict[str, Any]) -> bool:
    lower = {str(key).lower(): value for key, value in row.items()}
    category_text = " ".join(str(value).lower() for value in lower.values())
    has_interval_keys = any(key in lower for key in START_KEYS) and any(key in lower for key in END_KEYS)
    return has_interval_keys and (
        any(keyword in category_text for keyword in RALLY_KEYWORDS)
        or not any(key in lower for key in ("category", "label", "type", "class", "name"))
    )


def _interval_from_mapping(row: dict[str, Any]) -> Optional[Interval]:
    lower = {str(key).lower(): value for key, value in row.items()}
    start = _first_time_value(lower, START_KEYS)
    end = _first_time_value(lower, END_KEYS)
    if start is None or end is None or end <= start:
        return None
    return Interval(start_ms=start, end_ms=end)


def _first_time_value(row: dict[str, Any], keys: tuple[str, ...]) -> Optional[float]:
    for key in keys:
        if key in row:
            return _parse_time_value(row[key], is_ms=key.endswith("_ms") or key == "ms")
    return None


def _parse_time_value(value: Any, is_ms: bool = False) -> Optional[float]:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        number = float(value)
        return number if is_ms or number > 1000 else number * 1000.0

    text = str(value).strip()
    if not text:
        return None
    if re.fullmatch(r"\d+(?:\.\d+)?", text):
        number = float(text)
        return number if is_ms or number > 1000 else number * 1000.0

    parts = text.split(":")
    try:
        if len(parts) == 2:
            minutes = float(parts[0])
            seconds = float(parts[1])
            return (minutes * 60 + seconds) * 1000.0
        if len(parts) == 3:
            hours = float(parts[0])
            minutes = float(parts[1])
            seconds = float(parts[2])
            return (hours * 3600 + minutes * 60 + seconds) * 1000.0
    except ValueError:
        return None
    return None


def _coerce_positive_float(value: Any) -> Optional[float]:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _segment(
    category: str,
    start_ms: float,
    end_ms: float,
    reason: str,
    fps: float,
) -> SceneSegment:
    return SceneSegment(
        category=category,  # type: ignore[arg-type]
        start_ms=round(start_ms, 3),
        end_ms=round(end_ms, 3),
        confidence=1.0,
        reason=reason,
        source_frame_range=[
            max(0, int(start_ms / 1000.0 * fps)),
            max(0, int(end_ms / 1000.0 * fps)),
        ],
    )


def _video_duration_ms(video_path: Path, intervals: list[Interval]) -> float:
    try:
        import cv2  # type: ignore

        capture = cv2.VideoCapture(str(video_path))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        capture.release()
        if fps > 0 and frame_count > 0:
            return frame_count / fps * 1000.0
    except Exception:  # noqa: BLE001
        pass
    return max((interval.end_ms for interval in intervals), default=0.0)


def _video_fps(video_path: Path) -> float:
    try:
        import cv2  # type: ignore

        capture = cv2.VideoCapture(str(video_path))
        fps = float(capture.get(cv2.CAP_PROP_FPS) or 0.0)
        capture.release()
        return fps or 0.0
    except Exception:  # noqa: BLE001
        return 0.0


def _video_frame_count(video_path: Path) -> int:
    try:
        import cv2  # type: ignore

        capture = cv2.VideoCapture(str(video_path))
        frame_count = int(capture.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        capture.release()
        return frame_count
    except Exception:  # noqa: BLE001
        return 0


def _format_list(items: list[Any]) -> list[str]:
    if not items:
        return ["- None"]
    return [f"- `{item}`" for item in items]
