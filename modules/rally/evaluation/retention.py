from modules.rally.types import RallyInterval

def retained_time(predictions, truth, exclusions, duration_ms: float) -> dict:
    """Measure unions once, masking confirmed excluded time from both sides."""
    intervals = [(r.start_ms, r.end_ms) for r in predictions]
    targets = [(r.start_ms, r.end_ms) for r in truth if r.review_status == "verified"]
    ignored = [tuple(e["range_ms"]) for e in exclusions]
    breaks = sorted({0.0, duration_ms, *(max(0.0, min(duration_ms, x))
                     for row in intervals + targets + ignored for x in row)})
    totals = dict(target_ms=0.0, retained_target_ms=0.0, non_target_ms=0.0,
                  retained_non_target_ms=0.0, ignored_ms=0.0)
    for start, end in zip(breaks, breaks[1:]):
        midpoint = (start + end) / 2
        target = any(a <= midpoint < b for a, b in targets)
        prediction = any(a <= midpoint < b for a, b in intervals)
        excluded = not target and any(a <= midpoint < b for a, b in ignored)
        span = end - start
        if excluded:
            totals["ignored_ms"] += span
        elif target:
            totals["target_ms"] += span
            totals["retained_target_ms"] += span * prediction
        else:
            totals["non_target_ms"] += span
            totals["retained_non_target_ms"] += span * prediction
    return dict(**totals,
                target_retention=(totals["retained_target_ms"] / totals["target_ms"]
                                  if totals["target_ms"] else None),
                non_target_retention=(totals["retained_non_target_ms"] / totals["non_target_ms"]
                                      if totals["non_target_ms"] else None))

def offline_intervals(diagnostics: list[dict], config: dict, eof_ms: float) -> list[RallyInterval]:
    """Group observed motion with whole-file context; retain only supported spans.

    The online candidate requires a consecutive three-observation streak. This
    experiment admits sparse motion across a bounded gap and finalizes at EOF.
    It never fills a position or extrapolates a landing after the last motion.
    """
    groups: list[list[dict]] = []
    for row in diagnostics:
        if not row["motion"]:
            continue
        if not groups or row["timestamp_ms"] - groups[-1][-1]["timestamp_ms"] > config["gap_ms"]:
            groups.append([])
        groups[-1].append(row)
    intervals = []
    for rows in groups:
        if len(rows) < config["min_observations"]:
            continue
        start, end = rows[0]["timestamp_ms"], rows[-1]["timestamp_ms"]
        if end - start >= config["min_span_ms"]:
            intervals.append(RallyInterval(len(intervals) + 1, start, end, eof_ms))
    return intervals
