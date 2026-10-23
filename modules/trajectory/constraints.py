"""Output-time court and net-side constraints for displayed shot paths."""
from __future__ import annotations

from copy import deepcopy
import math


COURT_BOUNDS = (0.0, 5.18, 0.0, 13.4)
NET_Y = 6.7
PLAYER_TIME_TOLERANCE_MS = 220.0


def _point(value):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        point = tuple(map(float, value))
    except (TypeError, ValueError):
        return None
    return point if all(math.isfinite(v) for v in point) else None


def _in_court(point):
    left, right, far, near = COURT_BOUNDS
    return point is not None and left <= point[0] <= right and far <= point[1] <= near


def _side(point):
    if point is None or point[1] == NET_Y:
        return None
    return "far" if point[1] < NET_Y else "near"


def _opposite_sides(start, end):
    return start is not None and end is not None and (_side(start) is not None) and (_side(end) is not None) and _side(start) != _side(end)


def _rejection_reasons(start, end):
    reasons = []
    if not _in_court(start):
        reasons.append("start_out_of_court")
    if not _in_court(end):
        reasons.append("end_out_of_court")
    if not _opposite_sides(start, end):
        reasons.append("end_not_on_opposite_net_side")
    return reasons


def _start_rejection_reasons(start, hit_side):
    reasons = []
    if not _in_court(start):
        reasons.append("start_out_of_court")
    if start is not None and _side(start) is None:
        reasons.append("start_on_net_line")
    if hit_side in ("far", "near") and start is not None and _side(start) not in (None, hit_side):
        reasons.append("start_wrong_hit_side")
    return reasons


def _player_position(shot, player_tracks):
    """Return a same-side exact or bounded interpolation from player tracks."""
    diagnostics = shot.get("diagnostics")
    if not player_tracks or not isinstance(diagnostics, dict) or diagnostics.get("hit_side") not in ("far", "near"):
        return None
    side = diagnostics["hit_side"]
    try:
        target = float(shot["start_ms"])
    except (KeyError, TypeError, ValueError):
        return None
    if not math.isfinite(target):
        return None

    samples = []
    for record in player_tracks:
        try:
            timestamp = float(record["timestamp_ms"])
        except (KeyError, TypeError, ValueError):
            continue
        if not math.isfinite(timestamp):
            continue
        for player in record.get("players", []):
            if player.get("side") == side:
                point = _point(player.get("xy"))
                if point is not None:
                    samples.append((timestamp, point))
    samples.sort(key=lambda item: item[0])
    exact = next(((timestamp, point) for timestamp, point in samples if timestamp == target), None)
    if exact is not None:
        timestamp, point = exact
        return point, {"method": "exact", "source_times_ms": [timestamp]}

    before = next(((timestamp, point) for timestamp, point in reversed(samples) if timestamp < target), None)
    after = next(((timestamp, point) for timestamp, point in samples if timestamp > target), None)
    if before is None or after is None:
        return None
    before_time, before_point = before
    after_time, after_point = after
    if target - before_time > PLAYER_TIME_TOLERANCE_MS or after_time - target > PLAYER_TIME_TOLERANCE_MS:
        return None
    fraction = (target - before_time) / (after_time - before_time)
    point = tuple(a + fraction * (b - a) for a, b in zip(before_point, after_point))
    return point, {"method": "interpolated", "source_times_ms": [before_time, after_time]}


def _valid_point_for_side(point, side):
    return _in_court(point) and _side(point) is not None and (side not in ("far", "near") or _side(point) == side)


def constrain_shots(shots: list[dict], player_tracks: list[dict] | None = None) -> list[dict]:
    """Return a copy with invalid non-final arrows repaired or hidden.

    Unknown interval placeholders have no start point and are skipped when
    finding the last real hit or its next hit. A real unresolved last hit still
    counts as the final hit. Player positions repair only invalid starts and
    are estimated from the same hit side, with no extrapolation.
    """
    result = deepcopy(shots)
    groups: dict[object, list[int]] = {}
    for index, shot in enumerate(result):
        if not isinstance(shot, dict):
            continue
        rally_id = shot.get("rally_id")
        key = rally_id if rally_id is not None else ("unassigned", index)
        groups.setdefault(key, []).append(index)

    for indexes in groups.values():
        def start_order(index):
            try:
                value = float(result[index].get("start_ms", index))
            except (TypeError, ValueError):
                value = float(index)
            return (value if math.isfinite(value) else float(index), index)

        indexes.sort(key=start_order)
        real_hits = [i for i in indexes if _point(result[i].get("start_xy")) is not None]
        if len(real_hits) < 2:
            continue
        real_hit_positions = {idx: pos for pos, idx in enumerate(real_hits)}
        for index in real_hits[:-1]:
            shot = result[index]
            if shot.get("end_kind") == "unresolved":
                continue
            diagnostics = shot.get("diagnostics")
            if not isinstance(diagnostics, dict):
                diagnostics = {}
            existing = diagnostics.get("court_constraint")
            if isinstance(existing, dict) and existing.get("action") == "hidden":
                continue

            start = _point(shot.get("start_xy"))
            end = _point(shot.get("end_xy"))
            original_end = deepcopy(shot.get("end_xy"))
            original_end_kind = shot.get("end_kind")
            hit_side = diagnostics.get("hit_side")
            start_reasons = _start_rejection_reasons(start, hit_side)
            start_estimate = None
            if start_reasons:
                shot["diagnostics"] = diagnostics
                if not isinstance(existing, dict):
                    existing = {
                        "original_start_xy": deepcopy(shot.get("start_xy")),
                        "original_start_source": diagnostics.get("start_source"),
                        "original_end_xy": original_end,
                        "original_end_kind": original_end_kind,
                        "start_rejection_reasons": start_reasons,
                    }
                candidate = _player_position(shot, player_tracks)
                if candidate is not None:
                    estimated, estimate_info = candidate
                    start_estimate = {"xy": list(estimated), **estimate_info}
                    existing["start_rejection_reasons"] = start_reasons
                    existing["start_estimate"] = start_estimate
                    existing["start_estimate_accepted"] = _valid_point_for_side(estimated, hit_side)
                    existing["start_repaired"] = existing["start_estimate_accepted"]
                    if not existing["start_estimate_accepted"]:
                        existing["start_estimate_rejection_reasons"] = _start_rejection_reasons(estimated, hit_side)
                    shot["start_xy"] = list(estimated)
                    diagnostics["start_source"] = f"player_track_{estimate_info['method']}"
                    start = estimated
                start_reasons = _start_rejection_reasons(start, hit_side)

            next_hit = result[real_hits[real_hit_positions[index] + 1]]
            next_start = _point(next_hit.get("start_xy"))
            end_reasons = [reason for reason in _rejection_reasons(start, end) if reason != "start_out_of_court"]
            reasons = start_reasons + end_reasons
            if not reasons:
                if start_estimate is not None:
                    existing["action"] = "keep_after_start_repair"
                    existing["reason"] = []
                    diagnostics["court_constraint"] = existing
                continue

            replacement = next_start
            replacement_source = "next_hit_start_xy"
            replacement_reasons = _rejection_reasons(start, replacement)
            if start_reasons:
                replacement_reasons = list(dict.fromkeys(start_reasons + replacement_reasons))
            replacement_estimate = None
            if replacement_reasons:
                candidate = _player_position(next_hit, player_tracks)
                if candidate is not None:
                    estimated, estimate_info = candidate
                    replacement_estimate = {"xy": list(estimated), **estimate_info}
                    replacement = estimated
                    replacement_source = f"next_hit_player_track_{estimate_info['method']}"
                    replacement_reasons = list(dict.fromkeys(start_reasons + _rejection_reasons(start, replacement)))

            constraint = existing if isinstance(existing, dict) else {}
            constraint.update({
                "reason": reasons,
                "original_end_xy": constraint.get("original_end_xy", original_end),
                "original_end_kind": constraint.get("original_end_kind", original_end_kind),
                "replacement_start_xy": deepcopy(next_hit.get("start_xy")),
                "replacement_shot_id": next_hit.get("shot_id"),
                "replacement_source": replacement_source,
                "replacement_rejection_reasons": replacement_reasons,
            })
            if start_estimate is not None:
                constraint["start_estimate_accepted"] = existing["start_estimate_accepted"]
                constraint["start_repaired"] = existing["start_repaired"]
                if "start_estimate_rejection_reasons" in existing:
                    constraint["start_estimate_rejection_reasons"] = existing["start_estimate_rejection_reasons"]
            if replacement_estimate is not None:
                constraint["replacement_estimate"] = replacement_estimate
            constraint["action"] = "replace_end_with_next_hit" if not replacement_reasons else "hide_arrow"
            diagnostics["court_constraint"] = constraint
            shot["diagnostics"] = diagnostics
            if replacement_reasons:
                shot["end_xy"] = None
                shot["end_kind"] = "unresolved"
            else:
                shot["end_xy"] = list(replacement)
                shot["end_kind"] = "next_hit"

    return result
