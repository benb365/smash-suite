from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "apps/video-clipper/.runtime/opt08a-size"
REPORT = ROOT / "apps/video-clipper/reports/opt08a-size"
SIZES = ("288x512", "216x384", "144x256")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def merge(intervals):
    result = []
    for start, end in sorted((float(a), float(b)) for a, b in intervals if b > a):
        if result and start <= result[-1][1]:
            result[-1][1] = max(result[-1][1], end)
        else:
            result.append([start, end])
    return result


def difference(left, right):
    """Return portions of left intervals not covered by right intervals."""
    result = []
    right = merge(right)
    for start, end in merge(left):
        cursor = start
        for other_start, other_end in right:
            if other_end <= cursor:
                continue
            if other_start >= end:
                break
            if other_start > cursor:
                result.append([cursor, min(other_start, end)])
            cursor = max(cursor, other_end)
            if cursor >= end:
                break
        if cursor < end:
            result.append([cursor, end])
    return result


def compare_intervals(control, candidate):
    control = merge(control)
    candidate = merge(candidate)
    missing = difference(control, candidate)
    extra = difference(candidate, control)
    return {
        "control": control,
        "candidate": candidate,
        "missing_from_candidate": missing,
        "extra_in_candidate": extra,
        "missing_ms": sum(end - start for start, end in missing),
        "extra_ms": sum(end - start for start, end in extra),
    }


def point_differences(control_observations, candidate_observations):
    fields = ("x", "y", "confidence")
    counts = {field: 0 for field in fields}
    sums = {field: 0.0 for field in fields}
    maxima = {field: 0.0 for field in fields}
    total = 0
    point_rows = 0
    for baseline_call, candidate_call in zip(control_observations, candidate_observations):
        if baseline_call["call_index"] != candidate_call["call_index"]:
            raise AssertionError("observation calls are not index-aligned")
        old_points, new_points = baseline_call["points"], candidate_call["points"]
        if len(old_points) != len(new_points):
            raise AssertionError("observation point counts differ")
        for old, new in zip(old_points, new_points):
            point_rows += 1
            changed = False
            for field in fields:
                delta = abs(float(new[field]) - float(old[field]))
                sums[field] += delta
                maxima[field] = max(maxima[field], delta)
                if delta != 0:
                    counts[field] += 1
                    changed = True
            total += int(changed)
    if len(control_observations) != len(candidate_observations):
        raise AssertionError("observation call counts differ")
    return {
        "compared_points": point_rows,
        "points_with_any_changed_value": total,
        "changed_field_counts": counts,
        "absolute_delta_mean_by_field": {field: sums[field] / point_rows for field in fields},
        "absolute_delta_max_by_field": maxima,
        "interpretation": "Numeric output-difference diagnostics against the 288x512 control; not accuracy or ground truth.",
    }


def resource_summary(run_dir, run, stats, resources):
    samples = resources["process_samples"]
    intervals = [b["monotonic_s"] - a["monotonic_s"] for a, b in zip(samples, samples[1:])]
    mps = stats.get("mps_samples", [])
    rss = [row["rss_bytes"] for row in samples]
    cpu = [row["cpu_percent"] for row in samples]
    return {
        "process_sample_count": len(samples),
        "process_sampling_interval_seconds_max": max(intervals, default=None),
        "process_rss_sampled_peak_bytes": max(rss, default=None),
        "process_cpu_percent_sampled_mean": sum(cpu) / len(cpu) if cpu else None,
        "process_cpu_percent_sampled_max": max(cpu, default=None),
        "mps_sample_count": len(mps),
        "mps_allocated_sampled_peak_bytes": max((x["allocated_bytes"] for x in mps), default=None),
        "mps_driver_sampled_peak_bytes": max((x["driver_bytes"] for x in mps), default=None),
        "sampling_note": "Process RSS/CPU and MPS are independent approximately one-second samples; they are observed peaks, not continuous maxima.",
        "statistics_path": str(run_dir / "statistics.json"),
        "resources_path": str(run_dir / "resources.json"),
        "wall_seconds": run["recognition_wall_s"],
        "preflight_wall_seconds_outside_recognition": run["preflight_wall_s"],
        "outer_recognition_wall_seconds": run["outer_recognition_wall_s"],
        "phase_seconds": stats.get("seconds", {}),
    }


def main():
    REPORT.mkdir(parents=True, exist_ok=True)
    runs, results, stats, resources = {}, {}, {}, {}
    for size in SIZES:
        directory = RUNTIME / f"A-short-{size}"
        runs[size] = json.loads((directory / "run.json").read_text(encoding="utf-8"))
        results[size] = json.loads((directory / "result.json").read_text(encoding="utf-8"))
        stats[size] = json.loads((directory / "statistics.json").read_text(encoding="utf-8"))
        resources[size] = json.loads((directory / "resources.json").read_text(encoding="utf-8"))
        if runs[size]["status"] != "completed":
            raise AssertionError(f"incomplete run: {size}")
        observed = stats[size]["sources"][0]
        if (observed["frames_decoded"] != 4200 or observed["frames_delivered"] != 4200
                or observed["last_delivered_timestamp_ms"] != 167960):
            raise AssertionError(f"run did not reach expected EOF: {size}: {observed}")
        if len(runs[size]["predictor_observations"]) != 1400:
            raise AssertionError(f"wrong model call observation count: {size}")

    baseline, baseline_result = runs["288x512"], results["288x512"]
    old07a = json.loads((ROOT / "apps/video-clipper/reports/opt07a/summary.json").read_text(encoding="utf-8"))
    old_control = old07a["rows"][0]["variants"]["candidate"]
    control_raw, control_export = baseline_result["predictions"], baseline_result["export_ranges"]
    if control_raw != old_control["predictions"] or control_export != old_control["export_ranges"]:
        raise AssertionError("288x512 control differs from saved OPT-07A candidate A-short results")

    review_source = ROOT / "modules/models/tracknet/.runtime/opt08a-size-review.json"
    review_path = REPORT / "review.json"
    shutil.copyfile(review_source, review_path)
    screenshot_source = Path("/Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/opt08a-size/viewer.png")
    screenshot_path = REPORT / "viewer.png"
    shutil.copyfile(screenshot_source, screenshot_path)
    if sha256(review_source) != sha256(review_path) or sha256(screenshot_source) != sha256(screenshot_path):
        raise AssertionError("review evidence copy changed bytes")

    report = {
        "schema_version": 1,
        "scope": "One A-short full recognition run per input size; output and cost comparison only, without matching human labels.",
        "decision": "Do not adopt 216x384 or 144x256 in this round; do not run C-short or change production code. Changed outputs cannot be shown to preserve the required effect without matched human labels, so the conservative retention gate is not met.",
        "limitations": [
            "The baseline is this round's full 288x512 A-short control. Its raw predictions and selected export ranges exactly match the saved OPT-07A candidate.",
            "There are no matching human labels for this media. Candidate differences are not asserted to be missed truth, false positives, or an accuracy score.",
            "Each size is a single run; wall time and sampled resource differences are diagnostic observations, not stable performance claims.",
            "The viewer played 8 to 17 seconds; the screenshot captures the single 13.022-second point. No frame-by-frame review or human annotation was performed.",
        ],
        "inputs": {
            "case": "A-short",
            "video": baseline["video"],
            "video_sha256": baseline["video_sha256"],
            "frame_count_expected_and_decoded": 4200,
            "first_pts_ms": stats["288x512"]["sources"][0]["first_pts_ms"],
            "last_timestamp_ms": stats["288x512"]["sources"][0]["last_timestamp_ms"],
            "duration_ms": 168000,
            "weight": baseline["weights"],
        },
        "environment": {key: baseline.get(key) for key in ("git_commit", "python", "platform", "torch", "torchvision", "numpy", "opencv", "psutil", "device", "mps_available", "torch_threads", "opencv_threads")},
        "baseline_match_to_opt07a": {
            "comparison_source": "apps/video-clipper/reports/opt07a/summary.json rows[0].variants.candidate",
            "raw_predictions_equal": True,
            "export_ranges_equal": True,
        },
        "review_evidence": {
            "json": "apps/video-clipper/reports/opt08a-size/review.json",
            "json_sha256": sha256(review_path),
            "screenshot": "apps/video-clipper/reports/opt08a-size/viewer.png",
            "screenshot_sha256": sha256(screenshot_path),
            "observation": "The viewer played 8 to 17 seconds, and the screenshot captures the single 13.022-second point: both players are waiting on court; the 216x384 track retains this region while the control and 144x256 tracks omit it. No frame-by-frame review or human annotation was performed.",
        },
        "variants": {},
    }
    for size in SIZES:
        run_dir = RUNTIME / f"A-short-{size}"
        result, run = results[size], runs[size]
        observations = run["predictor_observations"]
        report["variants"][size] = {
            "input_size": run["input_size"],
            "status": run["status"],
            "actual_predictor_class": run["predictor_class"],
            "predictor_source_path": run["source_paths"]["predictor"],
            "source_predictor_sha256": run["source_predictor_sha256"],
            "derived_predictor_sha256": run["derived_predictor_sha256"],
            "runner_sha256": run["runner_sha256"],
            "code_sha256": run["code_sha256"],
            "git_status_at_run": run["git_status"],
            "derived_predictor_runtime_path": str(run_dir / "derived_predictor.py"),
            "recognition_wall_seconds": run["recognition_wall_s"],
            "recognition_wall_seconds_outer_check": run["outer_recognition_wall_s"],
            "preflight_wall_seconds_excluded": run["preflight_wall_s"],
            "torch_threads": run["torch_threads"],
            "opencv_threads": run["opencv_threads"],
            "workload": stats[size]["counts"],
            "raw_predictions": result["predictions"],
            "export_ranges_padding_500ms": result["export_ranges"],
            "diagnostics": result["details"],
            "point_differences_vs_288x512": None if size == "288x512" else point_differences(
                runs["288x512"]["predictor_observations"], observations),
            "interval_differences_vs_288x512": {
                "raw_by_prediction_order": [compare_intervals(
                    [[a["start_ms"], a["end_ms"]]], [[b["start_ms"], b["end_ms"]]])
                    for a, b in zip(baseline_result["predictions"], result["predictions"])],
                "export_by_selected_range_order": [compare_intervals([a], [b])
                    for a, b in zip(control_export, result["export_ranges"])],
                "raw_union": compare_intervals(
                    [[x["start_ms"], x["end_ms"]] for x in control_raw],
                    [[x["start_ms"], x["end_ms"]] for x in result["predictions"]]),
                "export_union": compare_intervals(control_export, result["export_ranges"]),
            },
            "resources": resource_summary(run_dir, run, stats[size], resources[size]),
            "evidence_directory": str(run_dir.relative_to(ROOT)),
        }
    report["summarizer_sha256"] = sha256(Path(__file__))
    (REPORT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
