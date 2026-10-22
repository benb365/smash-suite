from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
PRIMARY_ROOT = Path("/Users/bytedance/workspace/experiments/smash-suite")
GRAY_RUNTIME = ROOT / "apps/video-clipper/.runtime/opt08c-gray"
CONTROL_RUNTIME = PRIMARY_ROOT / "apps/video-clipper/.runtime/opt08a-size/A-short-288x512"
REPORT = ROOT / "apps/video-clipper/reports/opt08c-gray"
REVIEW_SOURCE = ROOT / "modules/models/tracknet/.runtime/opt08c-gray-review.json"
VIEWER_SOURCE = PRIMARY_ROOT / "apps/video-clipper/.runtime/opt08c-gray/viewer.png"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_size_summary_helpers():
    source = ROOT / "docs/ai/opt08a-size/summarize.py"
    spec = importlib.util.spec_from_file_location("_opt08c_size_summary_helpers", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_run(directory: Path):
    return {
        name: json.loads((directory / f"{name}.json").read_text(encoding="utf-8"))
        for name in ("run", "result", "statistics", "resources")
    }


def summarize_variant(directory: Path, data, helpers):
    run, result, stats, resources = (
        data["run"], data["result"], data["statistics"], data["resources"]
    )
    return {
        "evidence_directory": str(directory.relative_to(ROOT)) if directory.is_relative_to(ROOT) else str(directory),
        "status": run["status"],
        "input_size": run["input_size"],
        "input_channels": run.get("input_channels", 9),
        "actual_predictor_class": run["predictor_class"],
        "git_commit": run["git_commit"],
        "git_status_at_run": run["git_status"],
        "video_sha256": run["video_sha256"],
        "weights": run["weights"],
        "source_predictor_sha256": run["source_predictor_sha256"],
        "derived_predictor_sha256": run["derived_predictor_sha256"],
        "recognition_wall_seconds": run["recognition_wall_s"],
        "outer_recognition_wall_seconds": run["outer_recognition_wall_s"],
        "preflight_wall_seconds_excluded": run["preflight_wall_s"],
        "workload": stats["counts"],
        "phase_seconds": stats["seconds"],
        "sampled_resources": helpers.resource_summary(directory, run, stats, resources),
        "raw_predictions": result["predictions"],
        "selected_ranges_padding_500ms": result["export_ranges"],
        "padding_ms": result["padding_ms"],
        "details": result["details"],
    }


def main():
    helpers = load_size_summary_helpers()
    control = read_run(CONTROL_RUNTIME)
    candidate_dir = GRAY_RUNTIME / "A-short-gray3"
    candidate = read_run(candidate_dir)
    control_run, control_result = control["run"], control["result"]
    candidate_run, candidate_result = candidate["run"], candidate["result"]
    if control_run["status"] != "completed" or candidate_run["status"] != "completed":
        raise AssertionError("control and gray3 runs must both be completed")
    if control_run["video_sha256"] != candidate_run["video_sha256"]:
        raise AssertionError("control and candidate video hashes differ")
    if control_run["weights"]["ball_track.pt"]["sha256"] != candidate_run["weights"]["ball_track.pt"]["sha256"]:
        raise AssertionError("control and candidate weight hashes differ")

    baseline_predictor_mirror = CONTROL_RUNTIME / "derived_predictor.py"
    if sha256(baseline_predictor_mirror) != control_run["derived_predictor_sha256"]:
        raise AssertionError("main-directory color control predictor mirror SHA mismatch")
    if sha256(candidate_dir / "derived_predictor.py") != candidate_run["derived_predictor_sha256"]:
        raise AssertionError("gray3 derived predictor SHA mismatch")

    raw_diff = helpers.compare_intervals(
        [[x["start_ms"], x["end_ms"]] for x in control_result["predictions"]],
        [[x["start_ms"], x["end_ms"]] for x in candidate_result["predictions"]],
    )
    selected_diff = helpers.compare_intervals(control_result["export_ranges"], candidate_result["export_ranges"])
    per_prediction = [
        helpers.compare_intervals([[a["start_ms"], a["end_ms"]]], [[b["start_ms"], b["end_ms"]]])
        for a, b in zip(control_result["predictions"], candidate_result["predictions"])
    ]
    point_diff = helpers.point_differences(
        control_run["predictor_observations"], candidate_run["predictor_observations"]
    )

    probe_source = GRAY_RUNTIME / "probe/probe.json"
    probe_dest = REPORT / "probe.json"
    REPORT.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(probe_source, probe_dest)
    if sha256(probe_source) != sha256(probe_dest):
        raise AssertionError("probe evidence copy changed bytes")
    review_dest = REPORT / "review.json"
    viewer_dest = REPORT / "viewer.png"
    shutil.copyfile(REVIEW_SOURCE, review_dest)
    shutil.copyfile(VIEWER_SOURCE, viewer_dest)
    if sha256(REVIEW_SOURCE) != sha256(review_dest) or sha256(VIEWER_SOURCE) != sha256(viewer_dest):
        raise AssertionError("viewer review evidence copy changed bytes")
    probe = json.loads(probe_dest.read_text(encoding="utf-8"))

    report = {
        "schema_version": 1,
        "scope": "A-short gray3 single full recognition compared with the archived OPT-08A 288x512 color control; no matched human labels.",
        "decision": "Do not adopt gray3 in this round. The output changed and no matched human labels establish effect preservation. This result does not reject other grayscale designs.",
        "limitations": [
            "The color control is the archived OPT-08A 288x512 full run mirrored in the primary checkout; it was not rerun in this round.",
            "The baseline reference predictor came from the archived OPT-08A worktree. Its actual main-directory derived source mirror and SHA are recorded below.",
            "There are no matching human labels. Interval differences are output changes, not proven missed rallies or accuracy measures.",
            "Wall time and sampled resources are single-run observations, not stable performance claims.",
            "The probe samples only three A-short windows and is numeric diagnostic evidence, not EOF, full-clip equivalence, or a speed test.",
            "The synchronized viewer played source 3.000 to 11.020 seconds and sought to 3.715 seconds; this is local boundary evidence only, with no human-annotated start/end or full-clip review.",
        ],
        "input": {
            "case": "A-short",
            "video": control_run["video"],
            "video_sha256": control_run["video_sha256"],
            "frame_count": control["statistics"]["sources"][0]["frames_decoded"],
            "last_timestamp_ms": control["statistics"]["sources"][0]["last_timestamp_ms"],
            "weight": control_run["weights"],
        },
        "environment": {
            key: candidate_run.get(key)
            for key in ("git_commit", "python", "platform", "torch", "torchvision", "numpy", "opencv", "psutil", "device", "mps_available", "torch_threads", "opencv_threads")
        },
        "review_evidence": {
            "review_json": str(review_dest.relative_to(ROOT)),
            "review_json_link": "review.json",
            "review_json_sha256": sha256(review_dest),
            "review_json_bytes": review_dest.stat().st_size,
            "viewer_image": str(viewer_dest.relative_to(ROOT)),
            "viewer_image_link": "viewer.png",
            "viewer_image_sha256": sha256(viewer_dest),
            "viewer_image_bytes": viewer_dest.stat().st_size,
            "record": "The synchronized viewer played source 3.000–11.020 seconds, then sought to 3.715 seconds. At that frame the color row retained the interval while gray3 removed it. This is local boundary evidence only, with no human-annotated start/end or full-clip review.",
        },
        "code_comparison": {
            "control_git_commit": control_run["git_commit"],
            "candidate_git_commit": candidate_run["git_commit"],
            "same_production_predictor_sha256": control_run["source_predictor_sha256"] == candidate_run["source_predictor_sha256"],
            "production_predictor_sha256": candidate_run["source_predictor_sha256"],
            "color_control_main_directory_mirror": str(baseline_predictor_mirror),
            "color_control_main_directory_mirror_sha256": sha256(baseline_predictor_mirror),
            "color_control_archived_reference_sha256": control_run["reference_source_sha256"],
            "gray3_derived_predictor": str(candidate_dir / "derived_predictor.py"),
            "gray3_derived_predictor_sha256": candidate_run["derived_predictor_sha256"],
            "color_control_code_sha256": control_run["code_sha256"],
            "gray3_candidate_code_sha256": candidate_run["code_sha256"],
            "color_control_helper_runner_sha256": control_run["runner_sha256"],
            "gray3_helper_runner_sha256": candidate_run["runner_sha256"],
            "gray3_helper_runner_sha256_semantics": "OPT-08A full-recognition helper runner inherited by the candidate; the candidate's OPT-08C wrapper has its own hash below.",
            "gray3_opt08c_runner_sha256": candidate_run["opt08c_runner_sha256"],
            "recognize_source_sha256": candidate_run["code_sha256"]["recognize"],
            "tracknet_model_source_sha256": candidate_run["code_sha256"]["tracknet_model"],
        },
        "probe": {
            "copied_from": str(probe_source.relative_to(ROOT)),
            "report_link": "probe.json",
            "sha256": sha256(probe_dest),
            "scope": probe["scope"],
            "selected_frames": [frame for rows in probe["sample_selection"]["groups"]["gray3"] for frame in rows["frames"]],
            "gray9_gray3_comparisons": probe["gray9_gray3_comparisons"],
            "non_first_layer_state_matches_color9": probe["non_first_layer_state_matches_color9"],
        },
        "color_control": summarize_variant(CONTROL_RUNTIME, control, helpers),
        "gray3_candidate": summarize_variant(candidate_dir, candidate, helpers),
        "point_differences_vs_color_control": point_diff,
        "interval_differences": {
            "raw_union": raw_diff,
            "raw_by_prediction_order": per_prediction,
            "selected_ranges_union_padding_500ms": selected_diff,
        },
        "summary_script_sha256": sha256(Path(__file__)),
    }
    (REPORT / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
