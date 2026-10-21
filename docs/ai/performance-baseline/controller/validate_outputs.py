"""Validate completed performance-baseline artifacts; never rerun inference."""
from __future__ import annotations

import datetime as dt
import hashlib
import json
import math
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]
RUNTIME = ROOT / "apps/video-clipper/.runtime/performance-baseline"
GROUPS = [
    ("baseline", ["A-short", "A-long", "C-short", "C-long", "D-short", "D-long"], True),
    ("profile-A", ["A-short"], False),
    ("profile-C", ["C-short"], False),
    ("profile-D", ["D-short"], False),
    ("profile-native-A", ["A-short"], False),
]
PROFILE_PAIR = {"A-short": "profile-A", "C-short": "profile-C", "D-short": "profile-D"}


def read_json(path: Path):
    with path.open(encoding="utf-8") as stream:
        return json.load(stream)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def canonical(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def add_issue(record, message):
    record.setdefault("issues", []).append(message)


def resource_audit(path: Path, runner_summary):
    audit = {"path": str(path), "line_count": 0, "intervals_s": [], "intervals_over_1s": [],
             "errors": [], "observed_processes": [], "runner_pid_summary": runner_summary}
    if not path.is_file():
        audit["error"] = "resources.jsonl missing"
        return audit
    rows = []
    with path.open(encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                audit["errors"].append({"line": line_number, "parse_error": str(exc), "raw": line.rstrip()})
    audit["line_count"] = len(rows)
    processes = {}
    for row_index, row in enumerate(rows):
        interval = row.get("interval_s")
        if isinstance(interval, (int, float)):
            audit["intervals_s"].append(interval)
            if interval > 1:
                audit["intervals_over_1s"].append({"row": row_index, "interval_s": interval})
        for error in row.get("errors", []):
            audit["errors"].append({"row": row_index, "error": error})
        for proc in row.get("processes", []):
            processes[proc.get("pid")] = {"pid": proc.get("pid"), "parent_pid": proc.get("parent_pid"),
                                           "name": proc.get("name")}
    observed_pids = set(processes)
    runner_pids = set((runner_summary or {}).get("pids", []))
    missing_runner_pids = sorted(runner_pids - observed_pids)
    audit["runner_pids_missing_from_samples"] = missing_runner_pids
    roots = [proc for pid, proc in processes.items() if proc.get("parent_pid") not in observed_pids]
    backend = roots[0] if len(roots) == 1 else None
    worker = None
    ffmpeg = []
    if backend:
        worker_candidates = [proc for proc in processes.values()
                             if proc.get("parent_pid") == backend["pid"]
                             and "python" in str(proc.get("name", "")).casefold()]
        worker = worker_candidates[0] if worker_candidates else None
    for proc in processes.values():
        if "ffmpeg" in str(proc.get("name", "")).casefold():
            ffmpeg.append(proc)
    audit["observed_processes"] = sorted(processes.values(), key=lambda row: row["pid"] or -1)
    audit["process_roles"] = {"backend_root": backend, "worker_direct_child": worker, "ffmpeg": ffmpeg}
    audit["max_interval_s"] = max(audit["intervals_s"], default=None)
    audit["resource_errors_preserved"] = bool(audit["errors"])
    audit["coverage"] = {"backend": backend is not None, "worker": worker is not None, "ffmpeg": bool(ffmpeg)}
    return audit


def decode_output(path: Path, ffmpeg: str, log_path: Path):
    """Fully decode audio/video with FFmpeg, then count video frames and PTS with PyAV."""
    command = [ffmpeg, "-hide_banner", "-nostdin", "-v", "error", "-i", str(path),
               "-map", "0:v:0", "-map", "0:a?", "-f", "null", "-"]
    proc = subprocess.run(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=False)
    log_path.write_text("$ " + " ".join(command) + "\n" + proc.stderr, encoding="utf-8")
    result = {"path": str(path), "sha256": sha256(path), "bytes": path.stat().st_size,
              "ffmpeg_command": command, "ffmpeg_exit_code": proc.returncode,
              "ffmpeg_log": str(log_path), "video": None, "audio_streams": [], "issues": []}
    if proc.returncode != 0:
        result["issues"].append(f"FFmpeg full AV decode exited {proc.returncode}")
    try:
        import av
        with av.open(str(path)) as container:
            videos = list(container.streams.video)
            audios = list(container.streams.audio)
            if not videos:
                result["issues"].append("PyAV found no video stream")
                return result
            stream = videos[0]
            container_duration_s = (container.duration / av.time_base) if container.duration is not None else None
            video_duration_s = (float(stream.duration * stream.time_base)
                                if stream.duration is not None and stream.time_base is not None else None)
            frames = 0
            first_pts = last_pts = None
            non_monotonic_pts = []
            frame_sizes = set()
            time_base = float(stream.time_base) if stream.time_base else None
            for frame in container.decode(video=0):
                frames += 1
                frame_sizes.add((frame.width, frame.height))
                if frame.pts is None or time_base is None:
                    non_monotonic_pts.append({"frame": frames - 1, "reason": "missing PTS or time base"})
                    continue
                pts_s = float(frame.pts * stream.time_base)
                if first_pts is None:
                    first_pts = pts_s
                if last_pts is not None and pts_s <= last_pts:
                    non_monotonic_pts.append({"frame": frames - 1, "previous_s": last_pts, "current_s": pts_s})
                last_pts = pts_s
            layout = stream.codec_context.format.name if stream.codec_context.format else None
            result["container_duration_s"] = container_duration_s
            result["video"] = {"codec": stream.codec_context.name, "width": stream.width,
                               "height": stream.height, "pixel_format": layout,
                               "time_base": str(stream.time_base), "decoded_frames": frames,
                               "duration_s": video_duration_s,
                               "first_pts_s": first_pts, "last_pts_s": last_pts,
                               "observed_pts_span_s": (last_pts - first_pts) if first_pts is not None and last_pts is not None else None,
                               "frame_sizes": sorted([list(size) for size in frame_sizes]),
                               "pts_monotonic": not non_monotonic_pts,
                               "pts_issues": non_monotonic_pts}
            for audio in audios:
                layout_obj = audio.codec_context.layout
                result["audio_streams"].append({
                    "codec": audio.codec_context.name,
                    "sample_rate": audio.codec_context.sample_rate,
                    "channels": len(layout_obj.channels) if layout_obj else None,
                    "layout": layout_obj.name if layout_obj else None,
                    "time_base": str(audio.time_base),
                    "duration_s": (float(audio.duration * audio.time_base)
                                   if audio.duration is not None and audio.time_base is not None else None),
                })
            if frames == 0:
                result["issues"].append("PyAV decoded zero video frames")
            if non_monotonic_pts:
                result["issues"].append("Video PTS is missing or not strictly increasing")
            if frame_sizes != {(stream.width, stream.height)}:
                result["issues"].append("Decoded video frame dimensions vary from stream dimensions")
    except Exception as exc:
        result["issues"].append(f"PyAV inspection failed: {type(exc).__name__}: {exc}")
    return result


def inspect_case(group_name: str, case_id: str, statistics_expected: bool, ffmpeg: str, run_dir: Path):
    group = RUNTIME / group_name
    case_dir = group / case_id
    record = {"group": group_name, "case_id": case_id, "issues": []}
    manifest_path = group / "manifest.json"
    outer_path = case_dir / "result.json"
    evidence_dir = case_dir / "evidence"
    evidence_result_path = evidence_dir / "result.json"
    try:
        if not manifest_path.is_file():
            add_issue(record, f"missing {manifest_path}")
        else:
            record["manifest"] = str(manifest_path)
        outer = read_json(outer_path)
        record["runner_status"] = outer.get("status")
        record["kind"] = outer.get("kind")
        record["statistics_enabled"] = outer.get("statistics_enabled")
        if outer.get("status") != "completed":
            add_issue(record, f"runner status is {outer.get('status')!r}, expected 'completed'")
        if outer.get("kind") != ("baseline" if statistics_expected else "profile"):
            add_issue(record, f"runner kind is {outer.get('kind')!r}")
        if outer.get("statistics_enabled") is not statistics_expected:
            add_issue(record, f"statistics_enabled={outer.get('statistics_enabled')!r}, expected {statistics_expected}")
        state = outer.get("state") or {}
        if state.get("status") != "completed":
            add_issue(record, f"product job status is {state.get('status')!r}")
        if state.get("quality") != "balanced":
            add_issue(record, f"quality is {state.get('quality')!r}, expected 'balanced'")
        timings = outer.get("timings") or {}
        phase_keys = ("preparation_s", "recognition_s", "rendering_s")
        phases = {key: timings.get(key) for key in phase_keys}
        total = timings.get("total_s")
        if all(isinstance(phases[k], (int, float)) for k in phase_keys) and isinstance(total, (int, float)):
            phase_sum = math.fsum(phases.values())
            record["phase_timing_check"] = {"phases_s": phases, "sum_s": phase_sum,
                                             "total_s": total, "delta_s": phase_sum - total,
                                             "matches_with_float_precision_1e-9": math.isclose(phase_sum, total, rel_tol=1e-9, abs_tol=1e-9)}
            if not record["phase_timing_check"]["matches_with_float_precision_1e-9"]:
                add_issue(record, "three product phase timings do not sum to total within 1e-9 seconds")
        else:
            add_issue(record, "missing or invalid preparation/recognition/rendering/total timing fields")
        evidence_result = read_json(evidence_result_path)
        record["evidence_result"] = str(evidence_result_path)
        predictions = evidence_result.get("predictions")
        ranges = evidence_result.get("export_ranges")
        if not isinstance(predictions, list) or not predictions:
            add_issue(record, "evidence predictions are empty or invalid")
        if not isinstance(ranges, list) or not ranges:
            add_issue(record, "evidence export_ranges are empty or invalid")
        if evidence_result.get("quality") != "balanced":
            add_issue(record, f"evidence quality is {evidence_result.get('quality')!r}")
        if evidence_result.get("device") != "mps":
            add_issue(record, f"evidence device is {evidence_result.get('device')!r}, expected 'mps'")
        output_duration = evidence_result.get("output_duration_ms")
        range_duration = sum((float(pair[1]) - float(pair[0])) for pair in ranges) if isinstance(ranges, list) else None
        range_duration_matches = (
            isinstance(output_duration, (int, float)) and range_duration is not None
            and math.isclose(output_duration, range_duration, rel_tol=1e-12, abs_tol=1e-9)
        )
        record["range_duration_check"] = {"sum_ranges_ms": range_duration,
                                          "output_duration_ms": output_duration,
                                          "delta_ms": (output_duration - range_duration)
                                          if isinstance(output_duration, (int, float)) and range_duration is not None else None,
                                          "matches_with_float_precision": range_duration_matches,
                                          "comparison": "Float precision only: rel_tol=1e-12, abs_tol=1e-9 ms."}
        if not range_duration_matches:
            add_issue(record, "worker output_duration_ms does not equal summed export_ranges within float precision")
        state_duration = state.get("output_duration_ms")
        record["state_duration_check"] = {"state_output_duration_ms": state_duration,
                                           "worker_output_duration_ms": output_duration,
                                           "equal": state_duration == output_duration}
        if state_duration != output_duration:
            add_issue(record, "worker and product state output durations differ")
        if statistics_expected:
            stats_path = evidence_dir / "statistics.json"
            if not stats_path.is_file():
                add_issue(record, "baseline statistics.json missing")
            else:
                stats = read_json(stats_path)
                mps_samples = stats.get("mps_samples", [])
                valid_mps_samples = [row for row in mps_samples
                                     if isinstance(row.get("allocated_bytes"), (int, float))
                                     and row["allocated_bytes"] > 0]
                record["statistics"] = {"path": str(stats_path), "error": stats.get("error"),
                                         "phase_seconds": stats.get("seconds"), "counts": stats.get("counts"),
                                         "mps_sample_count": len(mps_samples),
                                         "valid_mps_sample_count": len(valid_mps_samples),
                                         "valid_mps_samples": valid_mps_samples,
                                         "mps_error_samples": [row for row in mps_samples if row.get("error") or row.get("unavailable")]}
                if stats.get("error") is not None:
                    add_issue(record, f"statistics recorded worker error: {stats.get('error')}")
                if not mps_samples:
                    add_issue(record, "baseline MPS samples are empty")
                if not valid_mps_samples:
                    add_issue(record, "baseline has no valid MPS sample with allocated_bytes > 0")
        else:
            if (evidence_dir / "statistics.json").exists():
                add_issue(record, "profile run unexpectedly has statistics.json")
        artifacts = outer.get("artifacts") or {}
        expected_output_sha = (artifacts.get("output.mp4") or {}).get("sha256")
        output_path = evidence_dir / "output.mp4"
        if not output_path.is_file():
            add_issue(record, "evidence output.mp4 missing")
        else:
            actual_output_sha = sha256(output_path)
            record["output_file"] = {"path": str(output_path), "bytes": output_path.stat().st_size,
                                     "expected_sha256": expected_output_sha, "actual_sha256": actual_output_sha,
                                     "sha_matches_runner": bool(expected_output_sha and expected_output_sha == actual_output_sha)}
            if not record["output_file"]["sha_matches_runner"]:
                add_issue(record, "output file SHA256 does not match runner artifact record")
            record["decoded_output"] = decode_output(output_path, ffmpeg, run_dir / f"{group_name}-{case_id}-ffmpeg.log")
            for issue in record["decoded_output"]["issues"]:
                add_issue(record, issue)
            if not record["decoded_output"].get("audio_streams"):
                add_issue(record, "decoded output has no audio stream; approved benchmark inputs retain audio")
            expected_video = (state.get("video") or {})
            decoded_video = record["decoded_output"].get("video") or {}
            expected_dimensions = (expected_video.get("width"), expected_video.get("height"))
            actual_dimensions = (decoded_video.get("width"), decoded_video.get("height"))
            record["state_video_dimensions_check"] = {
                "state_width_height": list(expected_dimensions),
                "decoded_width_height": list(actual_dimensions),
                "equal": expected_dimensions == actual_dimensions,
            }
            if expected_dimensions != actual_dimensions:
                add_issue(record, "decoded output dimensions do not match outer.state.video width/height")
        resources_path = case_dir / "resources.jsonl"
        resources = resource_audit(resources_path, outer.get("resources"))
        record["resources"] = resources
        if resources.get("error"):
            add_issue(record, resources["error"])
        if not resources.get("coverage", {}).get("backend"):
            add_issue(record, "resource tree did not identify a backend root process")
        if not resources.get("coverage", {}).get("worker"):
            add_issue(record, "resource tree did not identify a direct Python worker child")
        if not resources.get("coverage", {}).get("ffmpeg"):
            add_issue(record, "resource tree did not observe an FFmpeg process")
        if resources.get("runner_pids_missing_from_samples"):
            add_issue(record, "runner resource PID summary includes PIDs absent from raw samples")
    except Exception as exc:
        add_issue(record, f"inspection exception: {type(exc).__name__}: {exc}")
    return record


def compare_profile_pair(baseline_record, profile_record):
    comparison = {"case_id": baseline_record["case_id"], "baseline_group": "baseline",
                  "profile_group": profile_record["group"], "issues": []}
    for key in ("evidence_result",):
        baseline_path = Path(baseline_record.get(key, ""))
        profile_path = Path(profile_record.get(key, ""))
        if not baseline_path.is_file() or not profile_path.is_file():
            comparison["issues"].append(f"missing pair {key}")
            continue
        base = read_json(baseline_path)
        profile = read_json(profile_path)
        for field in ("predictions", "export_ranges"):
            equal = canonical(base.get(field)) == canonical(profile.get(field))
            comparison[field] = {"raw_canonical_equal": equal}
            if not equal:
                comparison["issues"].append(f"{field} differs between statistics ON and profile OFF")
    base_video = baseline_record.get("decoded_output") or {}
    profile_video = profile_record.get("decoded_output") or {}
    base_v, profile_v = base_video.get("video") or {}, profile_video.get("video") or {}
    base_signature = {"video_codec": base_v.get("codec"), "width": base_v.get("width"),
                      "height": base_v.get("height"), "audio_streams": base_video.get("audio_streams"),
                      "decoded_frames": base_v.get("decoded_frames")}
    profile_signature = {"video_codec": profile_v.get("codec"), "width": profile_v.get("width"),
                         "height": profile_v.get("height"), "audio_streams": profile_video.get("audio_streams"),
                         "decoded_frames": profile_v.get("decoded_frames")}
    comparison["output_structure"] = {"baseline": base_signature, "profile": profile_signature,
                                      "equal": base_signature == profile_signature}
    if base_signature != profile_signature:
        comparison["issues"].append("output video/audio structure or decoded frame count differs")
    return comparison


def main():
    if not RUNTIME.is_dir():
        print(f"Performance evidence directory missing: {RUNTIME}", file=sys.stderr)
        return 2
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    run_dir = RUNTIME / "output-validation" / f"run-{stamp}"
    run_dir.mkdir(parents=True, exist_ok=False)
    report_path = run_dir / "validation.json"
    report = {"schema_version": 1, "status": "in_progress", "created_at_utc": stamp,
              "scope": "Validate existing artifacts only; never rerun inference, alter inputs, or repair evidence.",
              "cases": [], "profile_comparisons": [], "issues": [],
              "expected_output_count": 10}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        manifest_path = RUNTIME / "baseline/manifest.json"
        if manifest_path.is_file():
            manifest = read_json(manifest_path)
            ffmpeg = manifest["environment"]["ffmpeg_executable"]
        else:
            report["issues"].append(f"missing baseline manifest: {manifest_path}")
            from modules.media.video import ffmpeg_exe
            ffmpeg = ffmpeg_exe()
        report["baseline_manifest"] = str(RUNTIME / "baseline/manifest.json")
        report["ffmpeg_executable"] = ffmpeg
        for group_name, case_ids, stats_expected in GROUPS:
            group_manifest_path = RUNTIME / group_name / "manifest.json"
            report.setdefault("manifests", {})[group_name] = str(group_manifest_path)
            if not group_manifest_path.is_file():
                report["issues"].append(f"missing group manifest: {group_manifest_path}")
            for case_id in case_ids:
                record = inspect_case(group_name, case_id, stats_expected, ffmpeg, run_dir)
                if group_name == "profile-native-A":
                    native_report = RUNTIME / "native-A-report.json"
                    record["native_profile_report"] = str(native_report)
                    record["native_profile_report_exists"] = native_report.is_file()
                    if not native_report.is_file():
                        add_issue(record, "native-A-report.json missing")
                report["cases"].append(record)
                report["issues"].extend(f"{group_name}/{case_id}: {issue}" for issue in record["issues"])
                report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        by_key = {(record["group"], record["case_id"]): record for record in report["cases"]}
        for case_id, profile_group in PROFILE_PAIR.items():
            comparison = compare_profile_pair(by_key[("baseline", case_id)], by_key[(profile_group, case_id)])
            report["profile_comparisons"].append(comparison)
            report["issues"].extend(f"{case_id} statistics ON/OFF: {issue}" for issue in comparison["issues"])
        native_comparison = compare_profile_pair(by_key[("baseline", "A-short")],
                                                 by_key[("profile-native-A", "A-short")])
        native_comparison["comparison_role"] = "supplemental native-profile recovery versus baseline A-short"
        report["profile_comparisons"].append(native_comparison)
        report["issues"].extend(f"A-short native supplemental profile: {issue}"
                                 for issue in native_comparison["issues"])
        report["actual_output_count"] = len(report["cases"])
        if report["actual_output_count"] != report["expected_output_count"]:
            report["issues"].append(
                f"inspected {report['actual_output_count']} outputs, expected {report['expected_output_count']}"
            )
        report["status"] = "failed" if report["issues"] else "passed"
    except Exception as exc:
        report["status"] = "failed"
        report["issues"].append(f"top-level inspection exception: {type(exc).__name__}: {exc}")
    finally:
        report["completed_at_utc"] = dt.datetime.now(dt.timezone.utc).isoformat()
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": report["status"], "report": str(report_path), "issue_count": len(report["issues"])}, ensure_ascii=False))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
