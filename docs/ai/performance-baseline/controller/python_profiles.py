"""Summarize saved py-spy Inferno SVG flame graphs without profiling processes."""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from xml.etree import ElementTree as ET

ROOT = Path(__file__).resolve().parents[4]
RUNTIME = ROOT / "apps/video-clipper/.runtime/performance-baseline"
WORKER_SOURCE = ROOT / "apps/video-clipper/backend/app/worker.py"
SVG_NS = "http://www.w3.org/2000/svg"
FG_NS = "http://github.com/jonhoo/inferno"
TITLE_RE = re.compile(r"^(.*?) \((.*?):(\d+)\) \(([\d,]+) samples, ([0-9.]+)%\)$")
ALL_RE = re.compile(r"^all \(([\d,]+) samples, ([0-9.]+)%\)$")
SAMPLE_RE = re.compile(r"Samples:\s*([\d,]+)\s+Errors:\s*([\d,]+)")


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def merge_intervals(intervals):
    merged = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], end))
        else:
            merged.append((start, end))
    return merged


def interval_count(intervals):
    return sum(end - start for start, end in merge_intervals(intervals))


def subtract_intervals(start, end, children):
    result = []
    cursor = start
    for child_start, child_end in merge_intervals(children):
        child_start, child_end = max(start, child_start), min(end, child_end)
        if child_start > cursor:
            result.append((cursor, child_start))
        cursor = max(cursor, child_end)
    if cursor < end:
        result.append((cursor, end))
    return result


def parse_svg(svg_path: Path):
    root = ET.parse(svg_path).getroot()
    frames = root.find(f".//{{{SVG_NS}}}svg[@id='frames']")
    if frames is None:
        raise ValueError("SVG has no svg element with id='frames'")
    total_samples = int(frames.attrib["total_samples"])
    nodes = []
    for group in list(frames):
        title = group.find(f"{{{SVG_NS}}}title")
        rect = group.find(f"{{{SVG_NS}}}rect")
        if title is None or rect is None:
            raise ValueError("frames child is missing required title or rect")
        title_text = title.text or ""
        match = TITLE_RE.fullmatch(title_text)
        all_match = ALL_RE.fullmatch(title_text)
        if not match and not all_match:
            raise ValueError(f"frame title does not match expected Inferno format: {title_text!r}")
        x = int(rect.attrib[f"{{{FG_NS}}}x"])
        width = int(rect.attrib[f"{{{FG_NS}}}w"])
        y = int(rect.attrib["y"])
        if match:
            function, filename, line = match.group(1), match.group(2), int(match.group(3))
            title_samples, title_percent = match.group(4), match.group(5)
        else:
            function, filename, line = "all", "<synthetic>", None
            title_samples, title_percent = all_match.group(1), all_match.group(2)
        nodes.append({"function": function, "filename": filename,
                      "line": line, "title_samples": int(title_samples.replace(",", "")),
                      "title_percent": float(title_percent), "x": x, "end": x + width,
                      "width": width, "y": y, "parent": None, "children": []})
    if not nodes:
        raise ValueError("frames element contains no function frames")

    by_y = defaultdict(list)
    for index, node in enumerate(nodes):
        by_y[node["y"]].append(index)
    levels = sorted(by_y)
    if len(levels) > 1 and len(set(b - a for a, b in zip(levels, levels[1:]))) != 1:
        raise ValueError(f"frame y levels are not evenly spaced: {levels}")
    step = (levels[1] - levels[0]) if len(levels) > 1 else None
    roots = []
    for index, node in enumerate(nodes):
        if step is None or node["y"] == levels[0]:
            roots.append(index)
            continue
        candidates = [parent_index for parent_index in by_y[node["y"] - step]
                      if nodes[parent_index]["x"] <= node["x"]
                      and nodes[parent_index]["end"] >= node["end"]]
        if not candidates:
            raise ValueError(f"frame has no containing parent at previous y level: {node}")
        parent_index = min(candidates, key=lambda item: nodes[item]["width"])
        node["parent"] = parent_index
        nodes[parent_index]["children"].append(index)

    for node in nodes:
        child_intervals = [(nodes[index]["x"], nodes[index]["end"]) for index in node["children"]]
        node["visible_residual_intervals"] = subtract_intervals(node["x"], node["end"], child_intervals)

    return total_samples, nodes, roots


def frame_label(node):
    location = node["filename"] if node["line"] is None else f"{node['filename']}:{node['line']}"
    return f"{node['function']} ({location})"


def is_recognize(node):
    return node["function"] == "recognize" and node["filename"].endswith("modules/rally/recognize.py")


def is_named_source_function(node, function, filename):
    return node["function"] == function and node["filename"].replace("\\", "/") == filename


def interval_overlap_count(first, second):
    overlap = []
    for left_start, left_end in merge_intervals(first):
        for right_start, right_end in merge_intervals(second):
            start, end = max(left_start, right_start), min(left_end, right_end)
            if end > start:
                overlap.append((start, end))
    return interval_count(overlap)


def aggregate(nodes, indices, denominator):
    grouped = defaultdict(lambda: {"inclusive": [], "visible_residual": [], "lines": set()})
    for index in indices:
        node = nodes[index]
        key = f"{node['function']} ({node['filename']})"
        grouped[key]["inclusive"].append((node["x"], node["end"]))
        grouped[key]["visible_residual"].extend(node["visible_residual_intervals"])
        grouped[key]["lines"].add(node["line"])
    records = []
    for key, spans in grouped.items():
        inclusive = interval_count(spans["inclusive"])
        visible_residual_count = interval_count(spans["visible_residual"])
        records.append({"frame": key, "lines": sorted(spans["lines"]),
                        "inclusive_samples": inclusive, "visible_residual_samples": visible_residual_count,
                        "inclusive_percent_of_denominator": (100 * inclusive / denominator) if denominator else None,
                        "visible_residual_percent_of_denominator": (100 * visible_residual_count / denominator) if denominator else None})
    return sorted(records, key=lambda item: (-item["inclusive_samples"], item["frame"]))


def descendants(nodes, roots):
    found = set()
    stack = list(roots)
    while stack:
        index = stack.pop()
        if index in found:
            continue
        found.add(index)
        stack.extend(nodes[index]["children"])
    return found


def function_rows(nodes, indices, pattern):
    selected = [index for index in indices if pattern(nodes[index])]
    return selected, aggregate(nodes, selected, interval_count(
        [(nodes[index]["x"], nodes[index]["end"]) for index in indices]))


def summarize_case(case: str):
    source_dir = RUNTIME / f"profile-control-{case}"
    svg_path = source_dir / "python-flamegraph.svg"
    log_path = source_dir / "py-spy.log"
    output_path = RUNTIME / "python-analysis" / case / "summary.json"
    correction_path = output_path.parent / "summary-correction-diagnostic.json"
    result = {"case": case, "status": "failed", "inputs": {}, "issues": [], "observations": []}
    try:
        if case == "C" and output_path.is_file() and not correction_path.exists():
            previous = json.loads(output_path.read_text(encoding="utf-8"))
            correction_path.parent.mkdir(parents=True, exist_ok=True)
            correction_path.write_text(json.dumps({
                "purpose": "Preserve prior summary claims superseded by the latest evidence-validity judgment.",
                "prior_status": previous.get("status"),
                "prior_sample_counts": previous.get("sample_counts"),
                "prior_handshake_wait_claim": previous.get("handshake_wait"),
                "prior_pose_entries_claim": (previous.get("targets") or {}).get("pose_entries"),
                "correction_basis": [
                    "Nonzero py-spy stack-unfold errors with parsed SVG and recognize coverage are limited evidence, not automatic whole-summary failure.",
                    "Original sampler warnings and both SVG/log sample counts remain recorded.",
                ],
            }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        for name, path in (("svg", svg_path), ("py_spy_log", log_path)):
            if not path.is_file():
                raise FileNotFoundError(f"required {name} missing: {path}")
            result["inputs"][name] = {"path": str(path), "bytes": path.stat().st_size,
                                      "sha256": file_sha256(path)}
        log_text = log_path.read_text(encoding="utf-8", errors="replace")
        log_match = SAMPLE_RE.search(log_text)
        if not log_match:
            raise ValueError("py-spy log has no Samples/Errors summary")
        collected, errors = (int(value.replace(",", "")) for value in log_match.groups())
        warning_lines = [line.strip() for line in log_text.splitlines() if "WARN" in line]
        sampling_error_lines = [line for line in warning_lines if "WARN  py_spy" in line]
        total, nodes, root_indices = parse_svg(svg_path)
        if total <= 0:
            raise ValueError(f"SVG total_samples must be positive, got {total}")
        recognize_roots = [index for index in root_indices if is_recognize(nodes[index])]
        # Recognize normally occurs below process frames, so find all matching frames
        # that have no matching recognize ancestor.
        if not recognize_roots:
            recognize_matches = [index for index, node in enumerate(nodes) if is_recognize(node)]
            recognize_roots = [index for index in recognize_matches
                               if not any(is_recognize(nodes[parent])
                                          for parent in ancestor_indices(nodes, index))]
        recognize_nodes = descendants(nodes, recognize_roots) if recognize_roots else set()
        visible_recognize_entry_union_samples = interval_count([(nodes[index]["x"], nodes[index]["end"])
                                                for index in recognize_roots])
        recognize_entries = [index for index, node in enumerate(nodes) if is_recognize(node)]
        recognize_visible_residual = interval_count([span for index in recognize_entries
                                         for span in nodes[index]["visible_residual_intervals"]])
        handshake_indices = [index for index, node in enumerate(nodes)
                             if node["function"] == "main"
                             and node["filename"].replace("\\", "/") == "app/worker.py"
                             and node["line"] == 52]
        handshake_spans = [(nodes[index]["x"], nodes[index]["end"]) for index in handshake_indices]
        recognize_spans = [(nodes[index]["x"], nodes[index]["end"]) for index in recognize_entries]
        handshake_samples = interval_count(handshake_spans)
        handshake_overlap = interval_overlap_count(handshake_spans, recognize_spans)
        handshake_source_line = None
        if WORKER_SOURCE.is_file():
            source_lines = WORKER_SOURCE.read_text(encoding="utf-8").splitlines()
            if len(source_lines) >= 52:
                handshake_source_line = source_lines[51].strip()
        source_mapping_valid = handshake_source_line == "time.sleep(.05)"
        all_indices = set(range(len(nodes)))
        all_rows = [row for row in aggregate(nodes, all_indices, total)
                    if not row["frame"].startswith("all (<synthetic>)")]
        recognize_rows = aggregate(nodes, recognize_nodes, visible_recognize_entry_union_samples) if recognize_nodes else []

        def matched(pattern, subset=all_indices, denominator=total):
            picked = [index for index in subset if pattern(nodes[index])]
            denominator_used = denominator
            rows = aggregate(nodes, picked, denominator_used)
            return {"matched_frame_count": len(picked), "visible_inclusive_union_samples": interval_count(
                        [(nodes[index]["x"], nodes[index]["end"]) for index in picked]),
                    "functions": rows}

        target_report = {
            "recognize": matched(is_recognize),
            "observe": matched(lambda n: is_named_source_function(n, "observe", "modules/rally/recognize.py")),
            "person_signals": matched(lambda n: is_named_source_function(n, "person_signals", "modules/rally/recognize.py")),
            "tracknet_predictor_entries": matched(lambda n: "modules/models/tracknet/predictor.py" in n["filename"]),
            "pose_entries": matched(lambda n: n["filename"].replace("\\", "/") in {
                "modules/models/keypoint_rcnn.py", "modules/models/keypoint_rcnn/__init__.py"}),
        }
        app_paths = lambda n: ("modules/rally/" in n["filename"]
                               or "modules/models/tracknet/" in n["filename"]
                               or n["filename"].replace("\\", "/") in {
                                   "modules/models/keypoint_rcnn.py", "modules/models/keypoint_rcnn/__init__.py"})
        concrete_all = matched(app_paths)
        concrete_recognize = matched(app_paths, recognize_nodes, visible_recognize_entry_union_samples) if recognize_nodes else {
            "matched_frame_count": 0, "visible_inclusive_union_samples": 0, "functions": []}
        result.update({
            "status": "parsed",
            "sample_counts": {"svg_total_samples": total, "py_spy_log_collected_samples": collected,
                              "py_spy_log_errors": errors, "svg_minus_log_samples": total - collected,
                              "counts_equal": total == collected},
            "warnings": warning_lines,
            "sampling_errors": {"count": errors, "raw_py_spy_warning_lines": sampling_error_lines,
                                "evidence_completeness": "partial" if errors else "no reported py-spy stack-unfold errors",
                                "underlying_cause": "unconfirmed" if errors else None},
            "frame_count": len(nodes),
            "recognize_coverage": {"found": bool(recognize_roots),
                                   "root_frames": [frame_label(nodes[index]) for index in recognize_roots],
                                   "visible_inclusive_entry_union_samples": visible_recognize_entry_union_samples,
                                   "percent_of_full_capture": 100 * visible_recognize_entry_union_samples / total,
                                   "visible_residual_samples": recognize_visible_residual,
                                   "percent_of_full_capture_visible_residual": 100 * recognize_visible_residual / total,
                                   "percent_of_visible_recognize_union_visible_residual":
                                       100 * recognize_visible_residual / visible_recognize_entry_union_samples if visible_recognize_entry_union_samples else None},
            "handshake_wait": {
                "svg_frames": [frame_label(nodes[index]) for index in handshake_indices],
                "samples": handshake_samples,
                "percent_of_full_capture": 100 * handshake_samples / total,
                "worker_source": str(WORKER_SOURCE),
                "worker_source_line_52": handshake_source_line,
                "source_mapping_valid": source_mapping_valid,
                "overlap_with_recognize_samples": handshake_overlap,
                "mutually_exclusive_from_recognize": handshake_overlap == 0,
                "quantifiable_wall_time_from_py_spy_samples": False,
                "algorithm_hotspot_included": False,
                "note": "Frame residency is not wall time; use benchmark-clock profile_ready to benchmark_start for full wait duration.",
            },
            "targets": target_report,
            "denominators": {"full_capture_samples": total,
                             "visible_recognize_entry_union_samples": visible_recognize_entry_union_samples},
            "top_30_frames_full_capture": all_rows[:30],
            "top_30_frames_below_visible_recognize_entries": recognize_rows[:30],
            "algorithm_hotspots_scope": "Only frames below visible recognize entries are included; handshake wait remains separate. Omitted narrow stack regions remain outside scope.",
            "concrete_python_frames": {"full_capture_denominator": concrete_all,
                                       "visible_recognize_entry_union_denominator": concrete_recognize},
            "inferno_min_width_percent_of_total_samples": 0.1,
            "interpretation_limits": [
                "Inferno omits frames narrower than 0.1% of total samples, so the SVG cannot recover omitted narrow appearances or exact full-stack coverage.",
                "The recognize denominator is only the interval union of visible recognize entry frames.",
                "Inclusive counts cover visible occurrences only; omitted narrow occurrences are absent.",
                "A visible node residual is an upper bound on exclusive own-frame residency at that visible node occurrence; aggregation can omit narrow occurrences and is not a full-function upper bound.",
                "Residual and inclusive sample counts are stack residency, not pure interpreter CPU time.",
                "Python waiting and native-library residency are not equated with Python computation.",
                "Samples/rate are not converted into wall-clock duration or actual baseline proportions.",
                "Inclusive frame totals use interval unions; visible residual samples are visible parent intervals minus visible direct-child interval unions.",
            ],
        })
        if total != collected:
            result["observations"].append(
                "SVG total_samples differs from py-spy log collected sample count; both are preserved"
            )
        if errors:
            result["observations"].append(
                f"py-spy reports {errors} sampling errors; preserve as local missing stack coverage without automatically invalidating parsed SVG"
            )
        if case == "A" and handshake_samples != 10427:
            result["issues"].append(f"A handshake frame union is {handshake_samples}, expected 10427")
        if case == "A" and not source_mapping_valid:
            result["issues"].append("A app/worker.py:52 does not map to time.sleep(.05) in checked source")
        if case == "A" and handshake_overlap != 0:
            result["issues"].append("A handshake and recognize sample intervals overlap")
        if not recognize_roots:
            result["issues"].append("recognize frame coverage not found in SVG")
        result["status"] = ("failed" if result["issues"] else
                             "passed_with_sampling_errors" if errors else "passed")
    except Exception as exc:
        result["issues"].append(f"{type(exc).__name__}: {exc}")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result, output_path


def ancestor_indices(nodes, index):
    parents = []
    parent = nodes[index]["parent"]
    while parent is not None:
        parents.append(parent)
        parent = nodes[parent]["parent"]
    return parents


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", nargs="+", choices=("A", "C", "D"), required=True,
                        help="explicit profile cases to summarize")
    args = parser.parse_args()
    summaries = []
    for case in args.cases:
        summary, path = summarize_case(case)
        summaries.append({"case": case, "status": summary["status"], "path": str(path),
                          "issues": summary["issues"]})
    print(json.dumps(summaries, ensure_ascii=False))
    accepted = {"passed", "passed_with_sampling_errors"}
    return 0 if all(item["status"] in accepted for item in summaries) else 1


if __name__ == "__main__":
    raise SystemExit(main())
