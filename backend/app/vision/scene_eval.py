from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, List, Sequence


@dataclass(frozen=True)
class Interval:
    start_ms: float
    end_ms: float

    @property
    def duration_ms(self) -> float:
        return max(0.0, self.end_ms - self.start_ms)


class ManualAnnotationNotVerifiedError(RuntimeError):
    pass


VERIFIED_REVIEW_STATUSES = {"verified", "human_verified", "reviewed", "accepted"}


def parse_manual_scene_intervals(text: str) -> List[Interval]:
    intervals: List[Interval] = []
    for line in text.splitlines():
        match = re.match(r"\s*(\d+):(\d+)\s*-\s*(\d+):(\d+)\s*$", line)
        if not match:
            continue

        start_minute, start_second, end_minute, end_second = map(int, match.groups())
        start_ms = float((start_minute * 60 + start_second) * 1000)
        end_ms = float((end_minute * 60 + end_second) * 1000)
        if end_ms > start_ms:
            intervals.append(Interval(start_ms=start_ms, end_ms=end_ms))

    return intervals


def load_manual_rally_annotations(
    path: str | Path,
    require_verified: bool = True,
) -> List[Interval]:
    annotation_path = Path(path)
    data = json.loads(annotation_path.read_text(encoding="utf-8"))
    segments = data.get("segments", [])
    if require_verified and not manual_annotation_is_verified(data):
        status = data.get("status", "unknown")
        raise ManualAnnotationNotVerifiedError(
            f"{annotation_path} is not human verified yet (status={status!r})."
        )

    intervals: List[Interval] = []
    for segment in segments:
        start_ms = _segment_time_ms(segment, "start")
        end_ms = _segment_time_ms(segment, "end")
        if end_ms > start_ms:
            intervals.append(Interval(start_ms=start_ms, end_ms=end_ms))
    return intervals


def manual_annotation_is_verified(annotation: dict[str, Any]) -> bool:
    if annotation.get("generation", {}).get("requires_human_review") is True:
        return False

    status = str(annotation.get("status", "")).lower()
    if status and status not in VERIFIED_REVIEW_STATUSES:
        return False

    segments = annotation.get("segments", [])
    if not segments:
        return False

    for segment in segments:
        review_status = str(segment.get("review_status", "")).lower()
        if review_status not in VERIFIED_REVIEW_STATUSES:
            return False
    return True


def scene_gate_rally_intervals(scene_gate_result: dict[str, Any]) -> List[Interval]:
    return [
        Interval(start_ms=float(segment["start_ms"]), end_ms=float(segment["end_ms"]))
        for segment in scene_gate_result.get("segments", [])
        if segment.get("category") == "rally"
    ]


def evaluate_rally_boundaries(
    predicted: Sequence[Interval],
    manual: Sequence[Interval],
    boundary_tolerance_ms: float = 2000.0,
) -> dict[str, Any]:
    predicted_clean = sorted(
        (interval for interval in predicted if interval.end_ms > interval.start_ms),
        key=lambda interval: interval.start_ms,
    )
    manual_merged = merge_intervals(manual)

    contained_manual: list[Interval] = []
    boundary_pass_manual: list[Interval] = []
    missed_manual: list[Interval] = []
    false_split_count = 0

    for manual_interval in manual_merged:
        overlapping_predictions = [
            predicted_interval
            for predicted_interval in predicted_clean
            if _overlaps(predicted_interval, manual_interval)
        ]
        containing_predictions = [
            predicted_interval
            for predicted_interval in overlapping_predictions
            if predicted_interval.start_ms <= manual_interval.start_ms
            and predicted_interval.end_ms >= manual_interval.end_ms
        ]
        if len(overlapping_predictions) > 1:
            false_split_count += 1
        if not containing_predictions:
            missed_manual.append(manual_interval)
            continue

        contained_manual.append(manual_interval)
        if any(
            manual_interval.start_ms - prediction.start_ms <= boundary_tolerance_ms
            and prediction.end_ms - manual_interval.end_ms <= boundary_tolerance_ms
            for prediction in containing_predictions
        ):
            boundary_pass_manual.append(manual_interval)

    false_merge_count = 0
    for predicted_interval in predicted_clean:
        overlapping_manual = [
            manual_interval
            for manual_interval in manual_merged
            if _overlaps(predicted_interval, manual_interval)
        ]
        if len(overlapping_manual) > 1:
            false_merge_count += 1

    return {
        "boundary_tolerance_ms": boundary_tolerance_ms,
        "manual_count": len(manual_merged),
        "predicted_count": len(predicted_clean),
        "containment_count": len(contained_manual),
        "containment_rate": round(safe_divide(len(contained_manual), len(manual_merged)), 4),
        "boundary_pass_count": len(boundary_pass_manual),
        "boundary_pass_rate_2s": round(
            safe_divide(len(boundary_pass_manual), len(manual_merged)),
            4,
        ),
        "missed_rally_count": len(missed_manual),
        "false_split_count": false_split_count,
        "false_merge_count": false_merge_count,
        "missed_manual_intervals": [interval_to_dict(interval) for interval in missed_manual],
    }


def evaluate_intervals(
    predicted: Sequence[Interval],
    manual: Sequence[Interval],
    tolerance_ms: float = 1000.0,
    min_false_positive_ms: float = 1000.0,
) -> dict[str, Any]:
    predicted_merged = merge_intervals(predicted)
    manual_merged = merge_intervals(manual)
    manual_for_precision = merge_intervals(expand_intervals(manual_merged, tolerance_ms))
    predicted_for_recall = merge_intervals(expand_intervals(predicted_merged, tolerance_ms))

    predicted_duration_ms = total_duration(predicted_merged)
    manual_duration_ms = total_duration(manual_merged)
    matched_prediction_ms = intersection_duration(predicted_merged, manual_for_precision)
    covered_manual_ms = intersection_duration(manual_merged, predicted_for_recall)
    union_ms = union_duration(predicted_merged, manual_for_precision)

    manual_hits = [
        interval
        for interval in manual
        if intersection_duration([interval], predicted_for_recall) > 0
    ]
    missed_manual = [
        interval
        for interval in manual
        if intersection_duration([interval], predicted_for_recall) <= 0
    ]
    false_positive_intervals = [
        interval
        for interval in subtract_intervals(predicted_merged, manual_for_precision)
        if interval.duration_ms >= min_false_positive_ms
    ]

    return {
        "tolerance_ms": tolerance_ms,
        "manual_count": len(manual),
        "predicted_count": len(predicted),
        "manual_duration_ms": round(manual_duration_ms, 3),
        "predicted_duration_ms": round(predicted_duration_ms, 3),
        "matched_prediction_ms": round(matched_prediction_ms, 3),
        "covered_manual_ms": round(covered_manual_ms, 3),
        "false_positive_ms": round(max(0.0, predicted_duration_ms - matched_prediction_ms), 3),
        "missed_manual_ms": round(max(0.0, manual_duration_ms - covered_manual_ms), 3),
        "precision": round(safe_divide(matched_prediction_ms, predicted_duration_ms), 4),
        "recall": round(safe_divide(covered_manual_ms, manual_duration_ms), 4),
        "f1": round(
            f1_score(
                safe_divide(matched_prediction_ms, predicted_duration_ms),
                safe_divide(covered_manual_ms, manual_duration_ms),
            ),
            4,
        ),
        "tolerant_iou": round(safe_divide(matched_prediction_ms, union_ms), 4),
        "manual_hit_count": len(manual_hits),
        "manual_hit_rate": round(safe_divide(len(manual_hits), len(manual)), 4),
        "manual_intervals": [interval_to_dict(interval) for interval in manual],
        "predicted_intervals": [interval_to_dict(interval) for interval in predicted],
        "missed_manual_intervals": [interval_to_dict(interval) for interval in missed_manual],
        "false_positive_intervals": [
            interval_to_dict(interval) for interval in false_positive_intervals
        ],
    }


def _segment_time_ms(segment: dict[str, Any], prefix: str) -> float:
    key = f"{prefix}_ms"
    if key in segment:
        return float(segment[key])

    time_key = f"{prefix}_time"
    if time_key in segment:
        return parse_timecode_ms(str(segment[time_key]))

    raise ValueError(f"Manual segment is missing {key!r} or {time_key!r}: {segment}")


def parse_timecode_ms(value: str) -> float:
    match = re.match(r"^\s*(?:(\d+):)?(\d+):(\d+)(?:\.(\d{1,3}))?\s*$", value)
    if not match:
        raise ValueError(f"Invalid timecode: {value!r}")

    hours_or_none, minutes_text, seconds_text, millis_text = match.groups()
    hours = int(hours_or_none or 0)
    minutes = int(minutes_text)
    seconds = int(seconds_text)
    milliseconds = int((millis_text or "0").ljust(3, "0"))
    return float(((hours * 60 + minutes) * 60 + seconds) * 1000 + milliseconds)


def _overlaps(left: Interval, right: Interval) -> bool:
    return left.start_ms < right.end_ms and left.end_ms > right.start_ms


def merge_intervals(intervals: Iterable[Interval]) -> List[Interval]:
    ordered = sorted(
        (interval for interval in intervals if interval.end_ms > interval.start_ms),
        key=lambda interval: interval.start_ms,
    )
    if not ordered:
        return []

    merged = [ordered[0]]
    for interval in ordered[1:]:
        previous = merged[-1]
        if interval.start_ms <= previous.end_ms:
            merged[-1] = Interval(
                start_ms=previous.start_ms,
                end_ms=max(previous.end_ms, interval.end_ms),
            )
        else:
            merged.append(interval)
    return merged


def expand_intervals(intervals: Iterable[Interval], tolerance_ms: float) -> List[Interval]:
    return [
        Interval(
            start_ms=max(0.0, interval.start_ms - tolerance_ms),
            end_ms=interval.end_ms + tolerance_ms,
        )
        for interval in intervals
    ]


def total_duration(intervals: Iterable[Interval]) -> float:
    return sum(interval.duration_ms for interval in merge_intervals(intervals))


def intersection_duration(left: Sequence[Interval], right: Sequence[Interval]) -> float:
    left_merged = merge_intervals(left)
    right_merged = merge_intervals(right)
    total = 0.0
    right_index = 0

    for left_interval in left_merged:
        while (
            right_index < len(right_merged)
            and right_merged[right_index].end_ms <= left_interval.start_ms
        ):
            right_index += 1

        scan_index = right_index
        while (
            scan_index < len(right_merged)
            and right_merged[scan_index].start_ms < left_interval.end_ms
        ):
            right_interval = right_merged[scan_index]
            total += max(
                0.0,
                min(left_interval.end_ms, right_interval.end_ms)
                - max(left_interval.start_ms, right_interval.start_ms),
            )
            scan_index += 1

    return total


def union_duration(left: Sequence[Interval], right: Sequence[Interval]) -> float:
    return total_duration([*left, *right])


def subtract_intervals(source: Sequence[Interval], blockers: Sequence[Interval]) -> List[Interval]:
    remaining = merge_intervals(source)
    for blocker in merge_intervals(blockers):
        next_remaining: List[Interval] = []
        for interval in remaining:
            if blocker.end_ms <= interval.start_ms or blocker.start_ms >= interval.end_ms:
                next_remaining.append(interval)
                continue
            if interval.start_ms < blocker.start_ms:
                next_remaining.append(
                    Interval(start_ms=interval.start_ms, end_ms=blocker.start_ms)
                )
            if blocker.end_ms < interval.end_ms:
                next_remaining.append(Interval(start_ms=blocker.end_ms, end_ms=interval.end_ms))
        remaining = next_remaining
    return remaining


def safe_divide(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def f1_score(precision: float, recall: float) -> float:
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def interval_to_dict(interval: Interval) -> dict[str, Any]:
    return {
        "start_ms": round(interval.start_ms, 3),
        "end_ms": round(interval.end_ms, 3),
        "start": format_ms(interval.start_ms),
        "end": format_ms(interval.end_ms),
        "duration_ms": round(interval.duration_ms, 3),
    }


def format_ms(value: float) -> str:
    total_ms = int(round(value))
    minutes, remainder = divmod(total_ms, 60_000)
    seconds, milliseconds = divmod(remainder, 1000)
    return f"{minutes:02d}:{seconds:02d}.{milliseconds:03d}"
