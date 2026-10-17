#!/usr/bin/env python3
"""Historical diagnosis only: no detector inference or new model baseline."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import asdict, fields, replace
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO_ROOT / "backend"))

from app.vision.rally_eval import evaluate_rallies, load_rally_annotations  # noqa: E402
from app.vision.rally_stream import RallyInterval  # noqa: E402
from app.vision.rally_segmentation import (  # noqa: E402
    RallySegmentationConfig,
    RallySignalBuilder,
    RallyStateMachine,
    _merge_close_rally_segments,
    _track_from_trace_dict,
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--trace", type=Path, default=REPO_ROOT / "models/yolo11n/.runtime/scene_gate/test_ysp_rally_segmentation_trace.jsonl")
    parser.add_argument("--saved-result", type=Path, default=REPO_ROOT / "models/yolo11n/.runtime/scene_gate/test_ysp_rally_segmentation.json")
    parser.add_argument("--output", type=Path, default=REPO_ROOT / "backend/tests/rally_benchmark/.runtime/legacy_comparison.json")
    parser.add_argument("--report", type=Path, default=Path(__file__).resolve().parent / ".runtime/legacy_comparison.md")
    args = parser.parse_args()
    manifest_path = REPO_ROOT / "datasets/badminton-v1/manifests/rally-benchmark.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    sample = next(row for row in manifest["samples"] if row["sample_id"] == "ysp-singles-seed")
    annotations = load_rally_annotations(REPO_ROOT / sample["annotations"])
    truth = [row for row in annotations if row.review_status == "verified"]
    saved = json.loads(args.saved_result.read_text(encoding="utf-8"))
    if saved["fps"] != sample["fps"] or saved["frame_count"] != sample["frame_count"]:
        raise ValueError("Saved result does not match the seed manifest timebase.")
    config_names = {field.name for field in fields(RallySegmentationConfig)}
    base_config = RallySegmentationConfig(**{
        key: value for key, value in saved["config"].items() if key in config_names
    }).normalized()
    trace = [json.loads(line) for line in args.trace.read_text(encoding="utf-8").splitlines() if line.strip()]
    if not trace:
        raise ValueError("Historical trace is empty.")
    for previous, current in zip(trace, trace[1:]):
        if current["frame_id"] <= previous["frame_id"] or current["time_ms"] <= previous["time_ms"]:
            raise ValueError("Historical trace must have strictly increasing frame ids and times.")
    builder = RallySignalBuilder(base_config)
    base_signals = [
        builder.build(row["frame_id"], row["time_ms"], [_track_from_trace_dict(track) for track in row["tracks"]])
        for row in trace
    ]
    groups = {"inside": [], "outside": []}
    for signal in base_signals:
        inside = any(row.start_ms <= signal.time_ms <= row.end_ms for row in truth)
        groups["inside" if inside else "outside"].append(signal)
    cases = []
    for case_id, start_guard_ms, post_merge in (
        ("A", base_config.start_guard_ms, True),
        ("B", base_config.start_guard_ms, False),
        ("C", 0.0, True),
        ("D", 0.0, False),
    ):
        config = replace(base_config, start_guard_ms=start_guard_ms)
        state_machine = RallyStateMachine(config)
        segments = []
        for signal in base_signals:
            segments.extend(state_machine.process(signal))
        process_count = len(segments)
        last = base_signals[-1]
        tail = state_machine.flush(last.time_ms, last.frame_id)
        segments.extend(tail)
        if post_merge:
            segments = _merge_close_rally_segments(segments, config.merge_gap_ms)
        predictions = [
            RallyInterval(index, row.start_ms, row.end_ms, row.emitted_at_ms)
            for index, row in enumerate(segments, 1)
        ]
        metrics = evaluate_rallies(predictions, annotations)
        cases.append({
            "case": case_id,
            "algorithm_id": "legacy_person_tracking_state_machine",
            "config": asdict(config),
            "post_merge": post_merge,
            "raw_process_count": process_count,
            "eof_flush_count": len(tail),
            "metrics": metrics,
        })
    # Fail rather than silently treating a changed legacy implementation as the saved run.
    expected = [(row["start_ms"], row["end_ms"], row["emitted_at_ms"]) for row in saved["segments"] if row["category"] == "rally"]
    reproduced = [(row["start_ms"], row["end_ms"], row["emitted_at_ms"]) for row in cases[0]["metrics"]["predictions"]]
    if reproduced != expected:
        raise ValueError("Case A no longer reproduces the saved run; inspect legacy code/version.")
    files = {
        "manifest": manifest_path,
        "video": REPO_ROOT / sample["video"],
        "annotations": REPO_ROOT / sample["annotations"],
        "roi": REPO_ROOT / sample["roi"],
        "trace": args.trace,
        "saved_result": args.saved_result,
        "legacy_code": REPO_ROOT / "backend/app/vision/rally_segmentation.py",
        "legacy_models": REPO_ROOT / "backend/app/models.py",
        "stream_contract_code": REPO_ROOT / "backend/app/vision/rally_stream.py",
        "evaluator_code": REPO_ROOT / "backend/app/vision/rally_eval.py",
        "comparison_code": Path(__file__),
    }
    result = {
        "evidence_kind": "legacy_diagnostic_not_new_baseline",
        "dataset_version": manifest["dataset_version"],
        "python_version": sys.version,
        "sample": sample,
        "sha256": {name: sha256(path) for name, path in files.items()},
        "files": {name: str(path) for name, path in files.items()},
        "saved_performance_not_remeasured": saved["config"]["performance"],
        "signal_samples": {
            name: {
                "count": len(signals),
                "active_count": sum(signal.active for signal in signals),
                "active_fraction": sum(signal.active for signal in signals) / len(signals) if signals else None,
                "hit_like_count": sum(signal.hit_like for signal in signals),
            } for name, signals in groups.items()
        },
        "cases": cases,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(build_report(result), encoding="utf-8")
    print(f"Historical comparison: {args.output}")
    print(f"Report: {args.report}")
    return 0


def build_report(result: dict) -> str:
    lines = [
        "# 旧 Rally 分割实验：原因分析与对照",
        "",
        "本报告仅诊断历史尝试，不接受旧实现为新 baseline，也不作正式模型选型。固定机位单打，复用现有 verified 标注，未改变起止点定义或人审状态。",
        "",
        "## 可复现证据",
        "",
        "```bash",
        ".venv/bin/python backend/tests/rally_benchmark/compare_legacy.py",
        "```",
        "",
        "原始视频、人工标注、ROI、历史 trace、算法文件和评估器的 SHA-256，连同配置及逐回合匹配保存在 `backend/tests/rally_benchmark/.runtime/legacy_comparison.json`。旧 trace 是本地历史资产，不随代码发布；缺少时应明确报错，不下载模型或补造结果。",
        "",
        f"数据清单版本：`{result['dataset_version']}`；评估器：`{result['cases'][0]['metrics']['evaluator_version']}`。",
        "",
        "标注为 11 个回合，共 100 秒。旧输出 7 段，共 248.8 秒，包括一个不与真值重叠的预测。旧 containment 100% 表示回合被大区间包含，不表示一回合对应一段。",
        "",
        "## 对照结果",
        "",
        "只重新执行旧 track→signal→状态机路径，不重新运行人物检测。A 组必须精确重现保存的起止及输出时刻，否则脚本拒绝生成报告。",
        "",
        "| 组 | 起点补时 | 事后合并 | 输出段数 | 无重叠漏检 | 误切 | 误合并 | 无真值重叠预测 | 起点误差 P50 / P95 ms | 终点误差 P50 / P95 ms |",
        "| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for case in result["cases"]:
        metrics = case["metrics"]
        no_overlap = sum(not overlaps for overlaps in metrics["prediction_overlaps"].values())
        start, end = metrics["start_error_ms"], metrics["end_error_ms"]
        lines.append(
            f"| {case['case']} | {case['config']['start_guard_ms'] / 1000:g}s | {'有' if case['post_merge'] else '无'} | "
            f"{metrics['prediction_count']} | {metrics['missed_rally_count']} | {metrics['false_split_count']} | "
            f"{metrics['false_merge_count']} | {no_overlap} | {start['p50']:.1f} / {start['p95']:.1f} | {end['p50']:.1f} / {end['p95']:.1f} |"
        )
    lines.extend([
        "",
        "边界误差只对最大化总 temporal IoU 的一对一匹配计算；未匹配项另存。误切和误合并按匹配前的重叠数减一求和。不同组的匹配数量不同，因此不可只比较 P50/P95 忽略漏检、误报和未匹配项。",
        "",
        "B/D 真正绕过事后合并；单把 merge_gap_ms 设为 0 仍会合并重叠区间，不能代表禁用后处理。旧 process 记录 19 次输出，EOF flush 另补一段；A 再压缩为 7 段。旧正式报告记 2 次误合并，是统计了两段包含多个真值的预测；当前需求按超出的回合数统计为 5。",
        "",
        "## 原因与证据强度",
        "",
        "1. **已验证：信号缺少回合语义。** active 只来自两个人的检测框底边中心速度/加速度，hit_like 也只来自同一个脚点速度，不是击球检测。",
    ])
    inside, outside = result["signal_samples"]["inside"], result["signal_samples"]["outside"]
    lines.extend([
        f"   稀疏 trace 中，真实回合内 active 为 {inside['active_count']}/{inside['count']}（{inside['active_fraction']:.2%}），回合外为 {outside['active_count']}/{outside['count']}（{outside['active_fraction']:.2%}），hit_like 两组均为 0。这些是采样点统计，不是逐帧模型准确率。",
        "2. **已验证：补时和合并互相放大。** 统一向前补 10 秒扩大了开始误差，也缩短了预测之间的间隙；事后合并再把原始碎段粘成跨多个真实回合的大段。去掉它们会暴露漏检、碎片和误报，而不是自动得到可靠边界。",
        "3. **已验证：最终文件与在线输出不是同一结果。** process 已返回的区间会在整段结束后被合并；EOF flush 将未确认候选输出。这不满足新契约的一次输出及结束确认要求。新回放禁止 EOF 自动补完整回合。",
        "4. **已验证：历史评估口径容易掩盖问题。** containment 允许一个长预测同时覆盖多个真值；旧边界评估没有一对一匹配。新评估保留原始重叠关系，分别报告边界误差、未匹配项、漏检、误切、误合并和输出延迟。",
        "5. **待验证：检测框抖动、场地透视、人员选择。** 框底边中心不是真实脚踝，像素阈值随机位和画面尺度变化；场地分半来自 ROI 图像上下界的均值。需要对具体失败窗口核验，尚不能认定每个错误都由这些因素造成。",
        "6. **历史文字证据：SoloShuttlePose 未走到分割效果评估。** 旧测试 README 记载球场预处理扫描接近整段后失败，未生成回合；对应 spike_report 文件目前缺失，不能独立核验。它说明上游依赖曾阻断实验，不能据此判定追球路线无效。",
        "",
        "旧运行记录 309 秒视频用时 30.195 秒，但每 10 帧分析一次，即 25fps 输入只提供 2.5 个分析点/秒。10.234 倍吞吐不能代表完整帧率分析或新模型性能。状态机确认的是低运动，不是实际结束事件；输出延迟须与终点误差同时看。",
        "",
        "## 后续执行计划",
        "",
        "| 阶段 | 工作 | 交付与决策 |",
        "| --- | --- | --- |",
        "| 1：评测基础 | 同一帧/区间契约、懒加载回放、一对一 IoU 评估、版本/配置/哈希记录 | 本轮实施；历史对照只用来解释失败，不正式选择模型 |",
        "| 2：补回合数据 | 固定机位单打，连续窗口含发球前、完整回合和回合间隙；按需求定义复核边界，留新来源作未调参测试 | 与现有球场/人员辅助数据分开记录；少量探索数据不替代仓库 10/30 机位要求 |",
        "| 3：候选比较 | 先比较轻量时序视觉特征与人物信号；对弱项再试姿态或球轨迹辅助 | 每条路线使用相同帧输入与评估器；单靠脚点阈值只保留为失败对照 |",
        "| 4：选型与实现 | 按逐回合错误、跨来源表现、延迟和算力选路线；分别处理短回合、走动捡球、遮挡和流结束 | 提交选型记录后实现正式算法；旧代码清理单独变更 |",
        "",
        "规划估计：1 名开发者加人工标注审核，评测基础约 3–5 个工作日，数据与候选比较约 1–2 周，选型及验证约 1 周；数据审核与真实错误可能改变周期。多机位、音频、编码导出、测速和判线不在本轮范围。",
        "",
        "当前样片已被反复分析，不能再作为未接触的泛化测试集。回合边界口径见[需求文档](../../../docs/plan/rally-segmentation-requirement.md#回合边界定义)；既有标签仍需按该定义逐段复核，历史时间戳与审核记录保持不变。不预设准确率门槛，也不因单个样片结果接受模型架构。",
        "",
    ])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
