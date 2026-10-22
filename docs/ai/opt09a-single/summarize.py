from __future__ import annotations

import hashlib
import importlib.util
import json
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RUNTIME = ROOT / "apps/video-clipper/.runtime/opt09a-single"
DUAL = Path("/Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/opt07a/recognition/candidate/C-short")
PRESERVATION = Path("/Users/bytedance/workspace/experiments/smash-suite/docs/ai/opt07a/evidence-preservation.json")
REPORT = ROOT / "apps/video-clipper/reports/opt09a-single"
VIEWER_SOURCE = ROOT / "modules/models/tracknet/.runtime/opt09a-single-review.json"
DURATION_MS = 180000.3125
SCREENSHOT_SOURCE = Path("/Users/bytedance/workspace/experiments/smash-suite/apps/video-clipper/.runtime/opt09a-single/viewer.png")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def opt08a_helpers():
    path = ROOT / "docs/ai/opt08a-size/summarize.py"
    spec = importlib.util.spec_from_file_location("_opt09a_opt08a_summarize", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module, path


def intervals(result):
    return [[row["start_ms"], row["end_ms"]] for row in result["predictions"]]


def run_variant(name, directory, helpers):
    run = read_json(directory / "run.json")
    result = read_json(directory / "result.json")
    stats = read_json(directory / "statistics.json")
    resources = read_json(directory / "resources.json")
    observations = read_json(directory / "observations.json")
    if run["status"] != "completed":
        raise AssertionError(f"incomplete result: {directory}")
    source = stats["sources"][0]
    if (source["frames_decoded"] != 5400 or source["frames_delivered"] != 5400
            or source["last_delivered_timestamp_ms"] != 179967.0):
        raise AssertionError(f"candidate did not reach expected EOF: {name}: {source}")
    if observations["selected_frame_ids"] != list(range(5400)):
        raise AssertionError(f"selected frame IDs do not cover source: {name}")
    if (observations["selected_timestamps_ms"][0] != 0.0
            or observations["selected_timestamps_ms"][-1] != 179967.0
            or len(observations["selected_timestamps_ms"]) != 5400):
        raise AssertionError(f"selected timestamps do not reach expected EOF: {name}")
    if not observations["downstream_streams_equal"]:
        raise AssertionError(f"downstream observation streams differ: {name}")
    return {
        "name": name,
        "directory": str(directory),
        "status": run["status"],
        "run": run,
        "result": result,
        "statistics": stats,
        "resources_raw": resources,
        "observations": {
            key: value for key, value in observations.items()
            if key not in ("selected_observations", "selected_frame_ids", "selected_timestamps_ms", "model_windows")
        },
        "workload": stats["counts"],
        "resource_summary": helpers.resource_summary(directory, run, stats, resources),
    }


def main():
    helpers, helper_path = opt08a_helpers()
    REPORT.mkdir(parents=True, exist_ok=True)
    manifest_path = ROOT / "apps/video-clipper/reports/performance-first-round/inputs.json"
    manifest = read_json(manifest_path)
    case = next(row for row in manifest["cases"] if row["case_id"] == "C-short")
    preservation = read_json(PRESERVATION)
    preserved = {row["path"]: row for row in preservation["files"]}

    dual_files = {name: DUAL / name for name in ("run.json", "result.json", "statistics.json", "resources.json", "decisions.json")}
    for name, path in dual_files.items():
        entry = preserved.get(f"apps/video-clipper/.runtime/opt07a/recognition/candidate/C-short/{name}")
        if not entry or sha256(path) != entry["sha256"]:
            raise AssertionError(f"primary dual evidence did not match preservation manifest: {path}")
    dual_run, dual_result = read_json(dual_files["run.json"]), read_json(dual_files["result.json"])
    dual_stats, dual_resources = read_json(dual_files["statistics.json"]), read_json(dual_files["resources.json"])
    if dual_run["status"] != "completed" or dual_stats["sources"][0]["frames_delivered"] != 5400:
        raise AssertionError("saved dual control is incomplete")

    candidates = {
        name: run_variant(name, RUNTIME / f"C-short-{name}", helpers)
        for name in ("native", "shifted")
    }
    if any(item["run"]["video_sha256"] != case["sha256"] for item in candidates.values()):
        raise AssertionError("candidate video SHA differs from manifest")
    if any(item["run"]["weights"] != dual_run["weights"] for item in candidates.values()):
        raise AssertionError("weights differ from saved dual control")
    if candidates["native"]["observations"]["people_features_sha256"] != candidates["shifted"]["observations"]["people_features_sha256"]:
        raise AssertionError("people features differ between candidates")
    native_observations = read_json(RUNTIME / "C-short-native/observations.json")
    shifted_observations = read_json(RUNTIME / "C-short-shifted/observations.json")
    if native_observations["selected_timestamps_ms"] != shifted_observations["selected_timestamps_ms"]:
        raise AssertionError("selected observation PTS differ between candidates")
    for item in candidates.values():
        if item["result"]["details"]["recognition"]["selected_people"] != dual_result["details"]["recognition"]["selected_people"]:
            raise AssertionError(f"selected people differ from dual control: {item['name']}")

    baseline_raw = intervals(dual_result)
    baseline_export = dual_result["export_ranges"]
    variants = {
        "dual": {
            "status": "completed; primary OPT-07A preserved mirror, not rerun in this round",
            "source_run_path": str(dual_files["run.json"]),
            "preservation_manifest": str(PRESERVATION),
            "preservation_manifest_sha256": sha256(PRESERVATION),
            "evidence_sha256": {name: sha256(path) for name, path in dual_files.items()},
            "run": dual_run,
            "raw_predictions": dual_result["predictions"],
            "export_ranges_padding_500ms": dual_result["export_ranges"],
            "diagnostics": dual_result["details"],
            "workload": dual_stats["counts"],
            "resource_summary": helpers.resource_summary(DUAL, dual_run, dual_stats, dual_resources),
            "interval_differences_vs_dual": None,
        }
    }
    for name, item in candidates.items():
        variants[name] = {
            "status": item["status"],
            "run": item["run"],
            "observations_summary": item["observations"],
            "raw_predictions": item["result"]["predictions"],
            "export_ranges_padding_500ms": item["result"]["export_ranges"],
            "diagnostics": item["result"]["details"],
            "workload": item["workload"],
            "resource_summary": item["resource_summary"],
            "interval_differences_vs_dual": {
                "raw_union": helpers.compare_intervals(baseline_raw, intervals(item["result"])),
                "export_union": helpers.compare_intervals(baseline_export, item["result"]["export_ranges"]),
            },
        }

    report = {
        "schema_version": 1,
        "scope": "Three single C-short full-recognition results: saved OPT-07A dual control and one native/shifted candidate run each. Output/cost comparison only; no matched human labels.",
        "decision": "Do not adopt either single-group candidate; make no production change. The changed intervals have no SHA-matched human annotations to establish preserved user value. This decision applies to these two C-short candidates only.",
        "limitations": [
            "The dual result is a previously completed preserved primary-workspace mirror, not a fresh control run in this round. Its 97.745275167-second wall time is one observation from another run and is not a stable performance claim.",
            "The media has no SHA-matched human labels. Missing/extra intervals describe algorithm output differences only; they are not verified misses, false positives, or accuracy scores.",
            "No framewise point comparison is reported: the preserved dual mirror does not contain per-window predictor observations. Candidate selected observations are saved in their runtime evidence.",
            "Wall time and sampled resource peaks come from one run per variant; resource sampling is approximately once per second and may miss peaks.",
        ],
        "input": {
            "case": "C-short",
            "video": case["video"],
            "video_sha256": case["sha256"],
            "inputs_manifest": str(manifest_path),
            "inputs_manifest_sha256": sha256(manifest_path),
            "duration_ms": DURATION_MS,
            "decoded_frames": 5400,
            "first_pts_ms": 0.0,
            "last_delivered_timestamp_ms": 179967.0,
            "weights": dual_run["weights"],
        },
        "environment": {key: candidates["native"]["run"].get(key) for key in (
            "git_commit", "python", "platform", "torch", "torchvision", "numpy", "opencv", "psutil",
            "device", "mps_available", "torch_threads", "opencv_threads")},
        "comparison_method": {
            "intervals": "Union missing/extra uses docs/ai/opt08a-size/summarize.py compare_intervals; no positional zip of different rally counts.",
            "resources": "Uses docs/ai/opt08a-size/summarize.py resource_summary.",
            "people_features_equal_native_shifted": True,
            "selected_people_equal_to_dual": True,
            "selected_observation_frame_ids": "0..5399 with identical PTS in both candidates",
        },
        "variants": variants,
        "summarizer_sha256": sha256(Path(__file__)),
        "interval_helper_sha256": sha256(helper_path),
    }
    report_path = REPORT / "summary.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    viewer = {
        "schema_version": 1,
        "title": "C-short 单组与双组回合输出对比",
        "note": "仅展示本次实际算法区间。此视频没有SHA匹配的人工标签；缺少人工行，不代表人工审核或评估通过。",
        "primary_track": "shifted",
        "tracks": [
            {"id": "dual", "label": "OPT-07A 双组（保存的控制）", "role": "prediction"},
            {"id": "native", "label": "OPT-09A native 单组", "role": "prediction"},
            {"id": "shifted", "label": "OPT-09A shifted 单组", "role": "prediction"},
        ],
        "clips": [{
            "id": "C-short",
            "title": "C-short 完整 5400 帧",
            "video": str(Path(case["video"]).resolve()),
            "duration_ms": DURATION_MS,
            "media_offset_ms": 0,
            "note": "时间以首帧为零。",
            "intervals": {
                name: [{"id": str(row["rally_id"]), "start_ms": row["start_ms"], "end_ms": row["end_ms"]}
                       for row in (dual_result["predictions"] if name == "dual" else candidates[name]["result"]["predictions"])]
                for name in ("dual", "native", "shifted")
            },
            "issues": [
                {"label": "6–12秒：单组与双组输出差异窗口", "start_ms": 6000, "end_ms": 12000},
                {"label": "39.5–46秒：单组与双组输出差异窗口", "start_ms": 39500, "end_ms": 46000},
                {"label": "103–117秒：单组与双组输出差异窗口", "start_ms": 103000, "end_ms": 117000},
            ],
        }],
    }
    VIEWER_SOURCE.parent.mkdir(parents=True, exist_ok=True)
    viewer_bytes = json.dumps(viewer, ensure_ascii=False, indent=2).encode("utf-8")
    VIEWER_SOURCE.write_bytes(viewer_bytes)
    review_path = REPORT / "review.json"
    shutil.copyfile(VIEWER_SOURCE, review_path)
    if sha256(VIEWER_SOURCE) != sha256(review_path):
        raise AssertionError("review JSON copy changed bytes")
    screenshot_path = REPORT / "viewer.png"
    shutil.copyfile(SCREENSHOT_SOURCE, screenshot_path)
    if sha256(SCREENSHOT_SOURCE) != sha256(screenshot_path):
        raise AssertionError("viewer screenshot copy changed bytes")

    viewer_evidence = {
        "source": str(VIEWER_SOURCE),
        "source_sha256": sha256(VIEWER_SOURCE),
        "report_copy": str(review_path),
        "report_copy_sha256": sha256(review_path),
        "byte_identical": True,
        "screenshot_source": str(SCREENSHOT_SOURCE.resolve()),
        "screenshot_report_copy": str(screenshot_path.resolve()),
        "screenshot_sha256": sha256(screenshot_path),
        "screenshot_bytes": screenshot_path.stat().st_size,
        "truth_track": "omitted: no matching human labels",
        "viewer_review_status": "partial local playback and difference-location check completed; not full-video review, human rally-boundary annotation, or accuracy evaluation",
        "observation": "Controller played C source 6.018–12.020 s with all three timelines synchronized, then clicked the dual timeline at 8.135 s; UI showed dual/native retained and shifted removed. This local difference-location check does not establish rally boundaries or review the full video.",
    }
    report["viewer_evidence"] = viewer_evidence
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

    readme = f"""# OPT-09A C-short 单组找球试验

## 结论

本轮不采用 native 或 shifted 单组候选，也不改生产代码。两候选都完整处理 C-short 的 5400 帧，但区间输出相对保存的 OPT-07A 双组控制发生变化；当前没有 SHA 匹配的人工标签证明改变保留了目标效果，因此按授权规则保守不采用。这个判断只覆盖本次 C-short 候选。

## 结果入口

- [机器可读汇总](summary.json)：完整 raw/export 区间、并集差异、诊断、计算量、运行环境、代码和输入/权重来源 SHA。
- [查看器数据](review.json)：实际视频与三组实际输出，缺少人工 truth 行；差异窗口仅用于定位。
- 主控播放了 6.018–12.020 秒，三条时间轴同步；点击双组时间轴 8.135 秒时，界面显示 dual/native 保留而 shifted 删除。这只是局部差异定位，不是完整视频复核或人工回合标注。
- 原始截图：[viewer.png](viewer.png)；SHA256 `{sha256(screenshot_path)}`。截图逐字节复制自 primary runtime。

| 方案 | 识别墙钟 | TrackNet 调用 / 输入帧 | cache miss / hit | 输出回合数 |
|---|---:|---:|---:|---:|
| OPT-07A 双组保存控制 | 97.745 s | 3599 / 10797 | 5400 / 5397 | 9 |
| OPT-09A native 单组 | 53.246 s | 1800 / 5400 | 5400 / 0 | 10 |
| OPT-09A shifted 单组 | 52.132 s | 1801 / 5403 | 5400 / 3 | 8 |

单组两次都选择 900 张人物图、225 次人物检测调用、7170 个框；选中人物与双组控制相同。两候选 people feature SHA 相同，最终选中帧 ID 为 0–5399 且 PTS 相同。双组 97.745 秒来自另一轮已保存运行，不是本轮重跑或稳定性能结论。

## 输出变化

所有差异都是算法区间并集差异，不是已确认漏失、误报或准确率。native 相对双组 raw 少 5300 ms、多 10768 ms；导出区间（padding 500 ms）少 5300 ms、多 11768 ms。它新增 105.6–115.667 秒区间。shifted raw 少 3167 ms、多 2900 ms；导出少 4167 ms、多 2900 ms。shifted 没有保留原双组 7.7–10.8 秒首段，并将 91.5–103 秒区间延长到 105.9 秒。

单组 wall time 与采样资源来自每个候选的一次运行。采样约每秒一次，峰值不是连续监测；不同轮次的单次观察不能证明稳定收益。双组保存镜像没有逐窗口预测点，因此本报告不做逐点对照；候选实际逐帧 observations 保留在 runtime 证据目录，不复制进报告。

## 复核窗口

使用仓库固定视频查看器打开 [review.json](review.json)，检查 6–12 秒、39.5–46 秒和 103–117 秒。窗口名称只说明算法输出不同，不暗示人工判断。查看器播放与截图记录待主控补记。

## 证据来源

- 候选原始证据：`apps/video-clipper/.runtime/opt09a-single/C-short-native/` 与 `C-short-shifted/`。
- 双组控制：主目录已保存镜像 `apps/video-clipper/.runtime/opt07a/recognition/candidate/C-short/`，按 preservation 清单核验 SHA；未在本轮重跑。
- 代码基线 commit：`{candidates['native']['run']['git_commit']}`。recognize SHA `{candidates['native']['run']['code_sha256']['recognize']}`；原 predictor SHA `{candidates['native']['run']['code_sha256']['predictor']}`。
- 结果、各运行代码/权重/输入 SHA 及资源摘要见 [summary.json](summary.json)。
"""
    (REPORT / "README.md").write_text(readme, encoding="utf-8")


if __name__ == "__main__":
    main()
