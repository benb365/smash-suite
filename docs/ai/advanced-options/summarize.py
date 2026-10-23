"""Validate saved benchmark evidence and build the fixed video-review data."""
from __future__ import annotations

import json
import hashlib
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUN = ROOT / "apps/video-clipper/.runtime/advanced-options/20261023-native"
INPUTS = ROOT / "docs/ai/advanced-options/inputs.json"
REPORT = ROOT / "apps/video-clipper/reports/advanced-options/results-native.json"
SHOW_REPORT = ROOT / "apps/video-clipper/reports/advanced-options/show-paths-results.json"
BASELINE = ROOT / "apps/video-clipper/reports/performance-validation-20261023/baseline"
sys.path.insert(0, str(ROOT))

from modules.media.video import ffmpeg_exe, selected_ranges

FLAGS = ("limit_fps", "small_input", "grayscale", "dynamic_scan")
CASE_IDS = (
    "A-all-off", "C-all-off", "D-all-off",
    "A-new-default", "C-new-default", "D-new-default",
    "C-dynamic-on", "D-dynamic-on",
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def sha256(path: Path):
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def interval_rows(predictions):
    rows = []
    for index, row in enumerate(predictions, 1):
        rows.append(dict(id=str(row.get("rally_id", index)), start_ms=row["start_ms"], end_ms=row["end_ms"]))
    return rows


def interval_diff(baseline, candidate):
    baseline_set = {tuple(row) for row in baseline}
    candidate_set = {tuple(row) for row in candidate}
    result = dict(
        equal=baseline == candidate,
        baseline_count=len(baseline),
        candidate_count=len(candidate),
        exact_intervals_removed=[list(row) for row in baseline if tuple(row) not in candidate_set],
        exact_intervals_added=[list(row) for row in candidate if tuple(row) not in baseline_set],
    )
    if len(baseline) == len(candidate):
        result["index_boundary_deltas_ms"] = [
            dict(index=i, start=candidate[i][0] - baseline[i][0], end=candidate[i][1] - baseline[i][1])
            for i in range(len(baseline))
        ]
    return result


def verify_case(case_id, case, expected):
    folder = RUN / case_id
    benchmark = read_json(folder / "result.json")
    request = read_json(folder / "evidence/request.json")
    result = read_json(folder / "evidence/result.json")
    assert benchmark["status"] == "completed", (case_id, benchmark.get("error"))
    assert benchmark["input_sha256"] == case["sha256"], case_id
    assert benchmark["state"]["status"] == "completed", case_id
    assert request["options"]["camera_type"] == case["scene"]
    assert request["options"]["optimizations"] == expected, (case_id, request["options"].get("optimizations"))
    assert benchmark["state"]["optimizations"] == expected, case_id
    assert result["optimizations"] == expected, case_id
    recognition = result["recognition"]
    assert recognition["optimizations"] == expected, case_id
    assert recognition["max_fps"] == (35 if expected["limit_fps"] else None), case_id
    assert recognition["tracknet_color_mode"] == ("gray" if expected["grayscale"] else "rgb"), case_id
    expected_input_size = [184, 320] if expected["small_input"] else [288, 512]
    expected_content_size = [180, 320] if expected["small_input"] else [288, 512]
    assert recognition["tracknet_input_size"] == expected_input_size, case_id
    assert recognition["tracknet_content_size"] == expected_content_size, case_id
    assert ("dynamic_scan" in recognition) == expected["dynamic_scan"], case_id
    assert result["padding_ms"] == 500, case_id
    actual_ranges = result["export_ranges"]
    computed_ranges = selected_ranges(result["predictions"], request["video"]["duration_ms"], padding_ms=500)
    assert actual_ranges == computed_ranges, (case_id, actual_ranges, computed_ranges)
    output = folder / "evidence/output.mp4"
    assert output.is_file() and output.stat().st_size > 0, case_id
    decoded = subprocess.run([ffmpeg_exe(), "-nostdin", "-v", "error", "-i", str(output), "-f", "null", "-"],
                             capture_output=True, text=True, timeout=600)
    assert decoded.returncode == 0, (case_id, decoded.stderr[-2000:])
    timing = benchmark["timings"]
    return dict(
        case_id=case_id,
        input_sha256=case["sha256"],
        requested_optimizations=case.get("optimizations"),
        effective_optimizations=expected,
        recognition_parameters=dict(
            max_fps=recognition["max_fps"],
            tracknet_input_size=recognition["tracknet_input_size"],
            tracknet_content_size=recognition["tracknet_content_size"],
            tracknet_color_mode=recognition["tracknet_color_mode"],
        ),
        padding_ms=result["padding_ms"],
        predictions=result["predictions"],
        export_ranges=actual_ranges,
        timings=timing,
        output=dict(path=str(output), bytes=output.stat().st_size,
                    sha256=benchmark["artifacts"]["output.mp4"]["sha256"], full_decode="passed"),
        output_ranges_match_worker_result=True,
        actual_state_optimizations=benchmark["state"]["optimizations"],
    )


def verify_show_path_integration(default_a):
    folder = RUN / "show-paths/A-default-show-paths"
    benchmark = read_json(folder / "result.json")
    request = read_json(folder / "evidence/request.json")
    result = read_json(folder / "evidence/result.json")
    expected = dict(limit_fps=True, small_input=True, grayscale=True, dynamic_scan=True)
    assert benchmark["status"] == "completed" and benchmark["state"]["status"] == "completed"
    assert benchmark["input_sha256"] == json.loads((ROOT / "docs/ai/advanced-options/show-paths-inputs.json").read_text())["cases"][0]["sha256"]
    assert request["options"]["show_shot_paths"] is True
    assert request["options"]["optimizations"] == expected
    assert benchmark["state"]["optimizations"] == expected
    assert result["optimizations"] == expected
    assert result["recognition"]["optimizations"] == expected
    assert result["padding_ms"] == 500
    assert result["predictions"] == default_a["predictions"]
    assert result["export_ranges"] == default_a["export_ranges"]
    assert selected_ranges(result["predictions"], request["video"]["duration_ms"], 500) == result["export_ranges"]
    assert result["recognition"]["dynamic_scan"]
    assert result["recognition"]["tracknet_input_size"] == [184, 320]
    assert result["recognition"]["tracknet_content_size"] == [180, 320]
    artifacts = folder / "evidence"
    for name in ("shot-paths.json", "trajectory-overlay.ass", "ball-observations.jsonl"):
        assert (artifacts / name).is_file() and (artifacts / name).stat().st_size > 0, name
    assert "yolo11n.pt" in benchmark["weights"]
    assert Path(benchmark["weights"]["yolo11n.pt"]["source"]).is_file()
    output = artifacts / "output.mp4"
    decoded = subprocess.run([ffmpeg_exe(), "-nostdin", "-v", "error", "-i", str(output), "-f", "null", "-"],
                             capture_output=True, text=True, timeout=600)
    assert decoded.returncode == 0, decoded.stderr[-2000:]
    return dict(
        status="integrated-feature-verified",
        case_id="A-default-show-paths",
        input_sha256=benchmark["input_sha256"],
        show_shot_paths=request["options"]["show_shot_paths"],
        effective_optimizations=expected,
        predictions_equal_to_A_new_default=True,
        export_ranges_equal_to_A_new_default=True,
        padding_ms=result["padding_ms"],
        yolo_weight=benchmark["weights"]["yolo11n.pt"],
        yolo_weight_source="existing local model cache; no download",
        artifacts={name: dict(bytes=(artifacts / name).stat().st_size,
                              sha256=sha256(artifacts / name))
                    for name in ("shot-paths.json", "trajectory-overlay.ass", "ball-observations.jsonl", "output.mp4")},
        timings=benchmark["timings"],
        output_full_decode="passed",
        performance_comparison="integration-only; excluded from the eight-case performance comparison",
    )


def main():
    inputs = read_json(INPUTS)
    cases = {case["case_id"]: case for case in inputs["cases"]}
    assert set(CASE_IDS) <= cases.keys()
    summary = read_json(REPORT)
    assert summary["status"] == "completed" and len(summary["results"]) == 8
    cases_summary = {}
    for case_id in CASE_IDS:
        case = cases[case_id]
        if case_id.endswith("all-off"):
            expected = dict.fromkeys(FLAGS, False)
        elif case_id.endswith("new-default"):
            expected = dict(limit_fps=True, small_input=True, grayscale=True,
                            dynamic_scan=case["scene"] == "high")
            assert "optimizations" not in case, case_id
        else:
            expected = dict.fromkeys(FLAGS, True)
        cases_summary[case_id] = verify_case(case_id, case, expected)

    frozen_baseline = {}
    for prefix, case_id in (("A", "A-all-off"), ("C", "C-all-off"), ("D", "D-all-off")):
        old_dir = BASELINE / f"{prefix}-short"
        old_result_path, old_run_path = old_dir / "result.json", old_dir / "run.json"
        old_result, old_run = read_json(old_result_path), read_json(old_run_path)
        current_result_path = RUN / case_id / "evidence/result.json"
        current_result = read_json(current_result_path)
        same_input = old_run["video_sha256"] == cases[case_id]["sha256"]
        same_predictions = old_result["predictions"] == current_result["predictions"]
        same_ranges = old_result["export_ranges"] == current_result["export_ranges"]
        assert same_input and same_predictions and same_ranges, case_id
        frozen_baseline[case_id] = dict(
            status="output-identical-to-frozen-baseline",
            video_sha256=old_run["video_sha256"],
            old_run_git_commit=old_run["git_commit"],
            old_run_code_sha256=old_run["code_sha256"],
            old_result_json_sha256=sha256(old_result_path),
            current_result_json_sha256=sha256(current_result_path),
            predictions_equal=True,
            export_ranges_equal=True,
            old_baseline_timings_seconds=old_run["timings"],
            old_baseline_timings_comparison="archived reference only; not a same-session performance control",
        )

    baseline_by_scene = {cases[key]["scene"]: cases_summary[key]
                         for key in ("A-all-off", "C-all-off", "D-all-off")}
    comparisons = {}
    for case_id, measured in cases_summary.items():
        if case_id.endswith("all-off"):
            continue
        scene = cases[case_id]["scene"]
        baseline = baseline_by_scene[scene]
        base_total = baseline["timings"]["total_s"]
        run_total = measured["timings"]["total_s"]
        comparisons[case_id] = dict(
            comparison_baseline=f"{scene}-all-off",
            total_delta_s=run_total - base_total,
            total_reduction_fraction=(base_total - run_total) / base_total,
            recognition_delta_s=measured["timings"]["recognition_s"] - baseline["timings"]["recognition_s"],
            export_ranges=interval_diff(baseline["export_ranges"], measured["export_ranges"]),
        )

    review_clips = []
    prefixes = {"high": "A", "courtside": "C", "personal": "D"}
    for scene, case_id in (("high", "A-all-off"), ("courtside", "C-all-off"), ("personal", "D-all-off")):
        source_case = cases[case_id]
        prefix = prefixes[scene]
        variants = {
            "all_off": case_id,
            "product_default": f"{prefix}-new-default",
            "dynamic_on": f"{prefix}-new-default" if scene == "high" else f"{prefix}-dynamic-on",
        }
        intervals = {}
        for track_id, variant_id in variants.items():
            intervals[track_id] = interval_rows(cases_summary[variant_id]["predictions"])
        request = read_json(RUN / case_id / "evidence/request.json")
        review_clips.append(dict(
            id=case_id.removesuffix("-all-off"), title=case_id.removesuffix("-all-off"),
            video=source_case["video"], duration_ms=request["video"]["duration_ms"],
            media_offset_ms=request["video"]["first_pts_ms"],
            note="仅展示真实产品算法输出；未提供人工真值，因此不计算准确率。",
            intervals=intervals,
        ))
    review = dict(
        schema_version=1,
        title="A/C/D 高级选项真实短片对照",
        note="同一短片比较全关、产品默认与动态粗筛开启。没有人工真值；区间差异不代表准确率结论。",
        primary_track="product_default",
        tracks=[
            dict(id="all_off", label="全关", role="prediction"),
            dict(id="product_default", label="产品默认", role="prediction"),
            dict(id="dynamic_on", label="动态粗筛开启（A与默认相同）", role="prediction"),
        ],
        clips=review_clips,
    )
    review_path = RUN / "review.json"
    review_path.write_text(json.dumps(review, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = dict(
        schema_version=1,
        status="verified_single_run_per_case_no_accuracy_claim",
        host=read_json(RUN / "manifest.json")["environment"],
        run_manifest_sha256=summary["manifest_sha256"],
        cases=cases_summary,
        comparisons_to_all_off=comparisons,
        frozen_baseline_output_comparison=frozen_baseline,
        implementation_boundary=dict(
            benchmark_start_head=read_json(RUN / "manifest.json")["code"]["commit"],
            trajectory_overlay_integrated_head="4f1b7a1",
            measurement_note=("HEAD changed from the benchmark-start revision to 4f1b7a1 while cases ran; "
                              "the three old short baselines have identical predictions and export ranges. "
                              "A all-off and A default were recorded before the overlay integration and have no shot-paths.json. "
                              "C/D are unaffected by show_shot_paths because the worker gates the feature to high view. "
                              "The separate A show-paths case verifies the integrated feature."),
            a_without_overlay_cases=["A-all-off", "A-new-default"],
            c_d_show_flag_scope="high view only",
        ),
        shot_path_integration=verify_show_path_integration(cases_summary["A-new-default"]),
        review_data=str(review_path),
    )
    out = RUN / "summary.json"
    out.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(dict(status=report["status"], summary=str(out), review_data=str(review_path)), ensure_ascii=False))


if __name__ == "__main__":
    main()
