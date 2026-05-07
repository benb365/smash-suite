from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Iterable, List, Sequence


@dataclass(frozen=True)
class Interval:
    start_ms: float
    end_ms: float

    @property
    def duration_ms(self) -> float:
        return max(0.0, self.end_ms - self.start_ms)


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


def scene_gate_rally_intervals(scene_gate_result: dict[str, Any]) -> List[Interval]:
    return [
        Interval(start_ms=float(segment["start_ms"]), end_ms=float(segment["end_ms"]))
        for segment in scene_gate_result.get("segments", [])
        if segment.get("category") == "rally"
    ]


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
