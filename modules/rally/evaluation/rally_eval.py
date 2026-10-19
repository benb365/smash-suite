from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Sequence

from modules.rally.types import RallyInterval


EVALUATOR_VERSION = "rally-iou-v3"
EXCLUSION_POLICY = "fully_contained_without_truth_overlap"
BOUNDARY_TOLERANCE_MS = 1500.0


@dataclass(frozen=True)
class RallyAnnotation:
    rally_id: int
    start_ms: float
    end_ms: float
    review_status: str

    def __post_init__(self) -> None:
        if type(self.rally_id) is not int:
            raise ValueError("Annotation rally id must be an integer.")
        if not all(math.isfinite(value) for value in (self.start_ms, self.end_ms)):
            raise ValueError("Annotation times must be finite.")
        if self.start_ms > self.end_ms:
            raise ValueError("Annotation requires start_ms <= end_ms.")


def load_rally_annotations(path: str | Path) -> list[RallyAnnotation]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("generation", {}).get("requires_human_review") is True:
        raise ValueError("Annotation file still requires human review.")
    return [
        RallyAnnotation(row["rally_id"], row["start_ms"], row["end_ms"], row["review_status"])
        for row in data["segments"]
    ]


def load_rally_exclusions(path: str | Path) -> list[dict[str, Any]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if data.get("generation", {}).get("requires_human_review") is True:
        raise ValueError("Annotation file still requires human review.")
    return data.get("excluded_events", [])


def evaluate_rallies(
    predictions: Sequence[RallyInterval], annotations: Sequence[RallyAnnotation],
    *, excluded_events: Sequence[dict[str, Any]] = (),
) -> dict[str, Any]:
    """Maximum-total temporal IoU matching, preserving the pre-match overlap graph."""
    truth = [row for row in annotations if row.review_status == "verified"]
    for rows in (predictions, annotations):
        if len({row.rally_id for row in rows}) != len(rows):
            raise ValueError("Rally ids must be unique within each input.")
    if len({event["event_id"] for event in excluded_events}) != len(excluded_events):
        raise ValueError("Excluded event ids must be unique.")
    for event in excluded_events:
        if event["review_status"] != "human_confirmed":
            raise ValueError("Excluded events require human confirmation.")
        start, end = event["range_ms"]
        if not all(math.isfinite(value) for value in (start, end)) or start >= end:
            raise ValueError("Excluded event requires a finite positive time range.")
    ignored = []
    scored = []
    for prediction in predictions:
        contained_by = [event["event_id"] for event in excluded_events
                        if event["range_ms"][0] <= prediction.start_ms
                        and prediction.end_ms <= event["range_ms"][1]]
        if contained_by and not any(_temporal_iou(prediction, row) > 0 for row in truth):
            ignored.append(dict(prediction=asdict(prediction), event_ids=contained_by))
        else:
            scored.append(prediction)
    input_prediction_count = len(predictions)
    predictions = scored
    ious = [[_temporal_iou(prediction, actual) for actual in truth] for prediction in predictions]
    matches = _maximum_iou_matching(ious)
    matched_predictions = {prediction for prediction, _ in matches}
    matched_truth = {actual for _, actual in matches}
    prediction_overlaps = [
        [truth[j].rally_id for j, score in enumerate(row) if score > 0] for row in ious
    ]
    truth_overlaps = [
        [predictions[i].rally_id for i in range(len(predictions)) if ious[i][j] > 0]
        for j in range(len(truth))
    ]
    rows = []
    for i, j in matches:
        prediction, actual = predictions[i], truth[j]
        start_offset = prediction.start_ms - actual.start_ms
        end_offset = prediction.end_ms - actual.end_ms
        # Only outward padding is tolerated; cutting any target time is an error.
        start_error = max(0.0, start_offset, -BOUNDARY_TOLERANCE_MS - start_offset)
        end_error = max(0.0, -end_offset, end_offset - BOUNDARY_TOLERANCE_MS)
        rows.append({
            "prediction_id": prediction.rally_id,
            "truth_id": actual.rally_id,
            "temporal_iou": ious[i][j],
            "start_offset_ms": start_offset,
            "end_offset_ms": end_offset,
            "start_error_ms": start_error,
            "end_error_ms": end_error,
            "start_acceptable": start_error == 0,
            "end_acceptable": end_error == 0,
            "both_acceptable": start_error == 0 and end_error == 0,
            "output_latency_ms": prediction.emitted_at_ms - prediction.end_ms,
        })
    acceptance = {"truth_count": len(truth), "matched_count": len(rows)}
    for boundary in ("start", "end", "both"):
        count = sum(row[f"{boundary}_acceptable"] for row in rows)
        acceptance[f"{boundary}_acceptable_count"] = count
        acceptance[f"{boundary}_acceptable_rate"] = count / len(truth) if truth else None
    return {
        "evaluator_version": EVALUATOR_VERSION,
        "boundary_policy": {
            "outward_tolerance_ms": BOUNDARY_TOLERANCE_MS,
            "start_offset_range_ms": [-BOUNDARY_TOLERANCE_MS, 0.0],
            "end_offset_range_ms": [0.0, BOUNDARY_TOLERANCE_MS],
            "error_summary_population": "matched_boundaries_outside_acceptable_range",
            "acceptance_denominator": "all_verified_truth",
        },
        "boundary_acceptance": acceptance,
        "truth_count": len(truth),
        "prediction_count": len(predictions),
        "input_prediction_count": input_prediction_count,
        "exclusion_policy": EXCLUSION_POLICY,
        "excluded_events": list(excluded_events),
        "ignored_predictions": ignored,
        "excluded_annotation_ids": [row.rally_id for row in annotations if row.review_status != "verified"],
        "matches": rows,
        "missed_rally_count": sum(not overlaps for overlaps in truth_overlaps),
        "false_positive_count": sum(not overlaps for overlaps in prediction_overlaps),
        "false_split_count": sum(max(0, len(overlaps) - 1) for overlaps in truth_overlaps),
        "false_merge_count": sum(max(0, len(overlaps) - 1) for overlaps in prediction_overlaps),
        "start_error_ms": _summary([row["start_error_ms"] for row in rows if row["start_error_ms"] > 0]),
        "end_error_ms": _summary([row["end_error_ms"] for row in rows if row["end_error_ms"] > 0]),
        "output_latency_ms": _summary([row.emitted_at_ms - row.end_ms for row in predictions]),
        "unmatched_prediction_ids": [row.rally_id for i, row in enumerate(predictions) if i not in matched_predictions],
        "unmatched_truth_ids": [row.rally_id for j, row in enumerate(truth) if j not in matched_truth],
        "prediction_overlaps": dict(zip((row.rally_id for row in predictions), prediction_overlaps)),
        "truth_overlaps": dict(zip((row.rally_id for row in truth), truth_overlaps)),
        "predictions": [asdict(row) for row in predictions],
        "annotations": [asdict(row) for row in truth],
    }


def _temporal_iou(prediction: RallyInterval, actual: RallyAnnotation) -> float:
    intersection = min(prediction.end_ms, actual.end_ms) - max(prediction.start_ms, actual.start_ms)
    if intersection <= 0:
        return 0.0
    union = max(prediction.end_ms, actual.end_ms) - min(prediction.start_ms, actual.start_ms)
    return intersection / union


def _maximum_iou_matching(ious: list[list[float]]) -> list[tuple[int, int]]:
    """Rectangular Hungarian assignment; dummy columns allow unmatched predictions."""
    if not ious or not ious[0]:
        return []
    row_count, truth_count = len(ious), len(ious[0])
    column_count = truth_count + row_count
    costs = [[-score for score in row] + [0.0] * row_count for row in ious]
    u, v = [0.0] * (row_count + 1), [0.0] * (column_count + 1)
    assigned, previous = [0] * (column_count + 1), [0] * (column_count + 1)
    for row in range(1, row_count + 1):
        assigned[0] = row
        column = 0
        minimum, used = [math.inf] * (column_count + 1), [False] * (column_count + 1)
        while True:
            used[column] = True
            current_row = assigned[column]
            delta, next_column = math.inf, 0
            for candidate in range(1, column_count + 1):
                if used[candidate]:
                    continue
                reduced = costs[current_row - 1][candidate - 1] - u[current_row] - v[candidate]
                if reduced < minimum[candidate]:
                    minimum[candidate], previous[candidate] = reduced, column
                if minimum[candidate] < delta:
                    delta, next_column = minimum[candidate], candidate
            for candidate in range(column_count + 1):
                if used[candidate]:
                    u[assigned[candidate]] += delta
                    v[candidate] -= delta
                else:
                    minimum[candidate] -= delta
            column = next_column
            if assigned[column] == 0:
                break
        while column:
            assigned[column] = assigned[previous[column]]
            column = previous[column]
    return sorted(
        (assigned[column] - 1, column - 1)
        for column in range(1, truth_count + 1)
        if assigned[column] and ious[assigned[column] - 1][column - 1] > 0
    )


def _summary(values: list[float]) -> dict[str, float | int | None]:
    ordered = sorted(values)

    def percentile(fraction: float) -> float:
        index = (len(ordered) - 1) * fraction
        lower = int(index)
        upper = min(lower + 1, len(ordered) - 1)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (index - lower)

    return {
        "count": len(values),
        "mean": sum(values) / len(values) if values else None,
        "p50": percentile(0.5) if values else None,
        "p95": percentile(0.95) if values else None,
        "max": max(values) if values else None,
    }
