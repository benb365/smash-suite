#!/usr/bin/env python3
"""Summarize completed first-round benchmark runs without touching their evidence."""
from __future__ import annotations

import csv
import json
import math
from pathlib import Path
from typing import Any

# summarize.py -> controller -> performance-first-round -> ai -> docs -> repository root.
ROOT = Path(__file__).resolve().parents[4]
RUNS = ROOT / "apps/video-clipper/.runtime/performance-first-round"
OUTPUT = ROOT / "apps/video-clipper/reports/performance-first-round/measurement-summary"
MIB = 1024**2
GIB = 1024**3


def number(value: Any) -> float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    value = float(value)
    return value if math.isfinite(value) else None


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def read_resources(path: Path) -> tuple[list[dict[str, Any]], int]:
    rows: list[dict[str, Any]] = []
    malformed = 0
    if not path.exists():
        return rows, malformed
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            try:
                value = json.loads(line)
                if isinstance(value, dict):
                    rows.append(value)
                else:
                    malformed += 1
            except json.JSONDecodeError:
                malformed += 1
    return rows, malformed


def maximum(values: list[Any]) -> float | None:
    valid = [v for item in values if (v := number(item)) is not None]
    return max(valid) if valid else None


def minimum(values: list[Any]) -> float | None:
    valid = [v for item in values if (v := number(item)) is not None]
    return min(valid) if valid else None


def summarize(result_path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    result = load_json(result_path)
    case_dir = result_path.parent
    evidence = case_dir / "evidence"
    statistics_path = evidence / "statistics.json"
    clock_path = evidence / "benchmark-clock.json"
    statistics = load_json(statistics_path) if statistics_path.exists() else {}
    clock = load_json(clock_path) if clock_path.exists() else {}
    resources, malformed = read_resources(case_dir / "resources.jsonl")

    state = result.get("state") or {}
    timings = result.get("timings") or state.get("timings") or {}
    phase_seconds = statistics.get("seconds") or {}
    counts = statistics.get("counts") or {}
    mps = statistics.get("mps_samples") or []
    errors = sum(len(row.get("errors") or []) if isinstance(row.get("errors"), list)
                 else int(bool(row.get("errors"))) for row in resources)
    errors += malformed
    intervals = [row.get("interval_s") for row in resources]
    allocation = [number(row.get("allocated_bytes")) for row in mps]
    driver = [number(row.get("driver_bytes")) for row in mps]

    record = {
        "run": result_path.parent.parent.name,
        "case": case_dir.name,
        "status": result.get("status") or state.get("status"),
        "kind": result.get("kind"),
        "total_s": number(timings.get("total_s", state.get("elapsed_s"))),
        "preparation_s": number(timings.get("preparation_s")),
        "recognition_s": number(timings.get("recognition_s")),
        "rendering_s": number(timings.get("rendering_s")),
        "subitem_seconds": {key: number(value) for key, value in phase_seconds.items()},
        "work_counts": {key: int(value) if isinstance(value, int) else number(value)
                         for key, value in counts.items()},
        "cpu_peak_percent_single_core": maximum([row.get("cpu_percent") for row in resources]),
        "rss_peak_gib": (lambda v: v / GIB if v is not None else None)(
            maximum([row.get("rss_bytes") for row in resources])),
        "mps_allocated_peak_mib": (lambda v: v / MIB if v is not None else None)(
            maximum(allocation)),
        "mps_driver_peak_mib": (lambda v: v / MIB if v is not None else None)(
            maximum(driver)),
        "workspace_peak_mib": (lambda v: v / MIB if v is not None else None)(
            maximum([row.get("work_without_source_logical_bytes") for row in resources])),
        "workspace_logical_peak_mib": (lambda v: v / MIB if v is not None else None)(
            maximum([row.get("work_logical_bytes") for row in resources])),
        "disk_free_min_gib": (lambda v: v / GIB if v is not None else None)(
            minimum([row.get("disk_free_bytes") for row in resources])),
        "sample_count": len(resources),
        "max_interval_s": maximum(intervals),
        "sampling_error_count": errors,
        "statistics_error": statistics.get("error"),
        "benchmark_start_monotonic": number(clock.get("benchmark_start")),
        "resource_samples": resources,
        "mps_samples": mps,
    }
    return record, resources


def plot_record(record: dict[str, Any], output_path: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    start = record["benchmark_start_monotonic"]
    resources = record["resource_samples"]
    mps = record["mps_samples"]
    figure, axes = plt.subplots(4, 1, figsize=(11, 10), sharex=True)
    figure.suptitle(f'{record["run"]} / {record["case"]} — 资源观测')

    def plot_resource(axis: Any, field: str, scale: float, label: str, color: str) -> None:
        points = [(number(row.get("monotonic_s")), number(row.get(field))) for row in resources]
        points = [(t - start, value / scale if value is not None else math.nan)
                  for t, value in points if t is not None and start is not None]
        if points and any(math.isfinite(y) for _, y in points):
            axis.plot([x for x, _ in points], [y for _, y in points], color=color, linewidth=1)
            axis.set_ylabel(label)
            axis.grid(True, alpha=0.25)
        else:
            axis.text(0.5, 0.5, "无有效数据", ha="center", va="center", transform=axis.transAxes)
            axis.set_ylabel(label)
            axis.grid(True, alpha=0.25)

    plot_resource(axes[0], "cpu_percent", 1, "CPU (% 单核)", "#2563eb")
    plot_resource(axes[1], "rss_bytes", GIB, "RSS (GiB)", "#059669")
    mps_points = [(number(item.get("monotonic_s")), number(item.get("allocated_bytes")),
                   number(item.get("driver_bytes"))) for item in mps]
    mps_points = [(t - start, a / MIB if a is not None else math.nan,
                   d / MIB if d is not None else math.nan)
                  for t, a, d in mps_points if t is not None and start is not None]
    if mps_points and any(math.isfinite(a) or math.isfinite(d) for _, a, d in mps_points):
        x = [item[0] for item in mps_points]
        axes[2].plot(x, [item[1] for item in mps_points], label="allocated", linewidth=1)
        axes[2].plot(x, [item[2] for item in mps_points], label="driver", linewidth=1)
        axes[2].legend(loc="best")
        axes[2].set_ylabel("MPS (MiB)")
        axes[2].grid(True, alpha=0.25)
    else:
        axes[2].text(0.5, 0.5, "无有效数据", ha="center", va="center", transform=axes[2].transAxes)
        axes[2].set_ylabel("MPS (MiB)")
        axes[2].grid(True, alpha=0.25)
    plot_resource(axes[3], "work_without_source_logical_bytes", MIB,
                  "工作区（不含源文件，MiB）", "#d97706")
    axes[3].set_xlabel("相对 benchmark_start 的时间（秒）")
    figure.tight_layout(rect=(0, 0, 1, 0.97))
    figure.savefig(output_path, dpi=140)
    plt.close(figure)


def main() -> None:
    try:
        import matplotlib  # noqa: F401
    except ImportError as error:
        raise SystemExit("需要当前环境已有 matplotlib；脚本不会安装依赖。") from error
    matplotlib.rcParams["font.sans-serif"] = ["PingFang SC"]
    matplotlib.rcParams["axes.unicode_minus"] = False

    OUTPUT.mkdir(parents=True, exist_ok=True)
    records: list[dict[str, Any]] = []
    excluded: list[dict[str, str]] = []
    for result_path in sorted(RUNS.glob("*/*/result.json")):
        try:
            result = load_json(result_path)
        except (OSError, json.JSONDecodeError) as error:
            excluded.append({"path": str(result_path.relative_to(ROOT)), "reason": f"读取失败: {error}"})
            continue
        state = result.get("state") or {}
        status = result.get("status") or state.get("status")
        if status != "completed":
            excluded.append({"path": str(result_path.relative_to(ROOT)), "reason": f"status={status}"})
            continue
        try:
            record, _ = summarize(result_path)
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as error:
            excluded.append({"path": str(result_path.relative_to(ROOT)), "reason": f"摘要失败: {error}"})
            continue
        chart_name = f'{record["run"]}-{record["case"]}-resources.png'
        record["chart"] = chart_name
        records.append(record)
        plot_record(record, OUTPUT / chart_name)

    fixed = [
        "run", "case", "status", "kind", "total_s", "preparation_s", "recognition_s", "rendering_s",
        "cpu_peak_percent_single_core", "rss_peak_gib", "mps_allocated_peak_mib", "mps_driver_peak_mib",
        "workspace_peak_mib", "workspace_logical_peak_mib", "disk_free_min_gib", "sample_count",
        "max_interval_s", "sampling_error_count", "statistics_error", "chart",
    ]
    phase_keys = sorted({key for record in records for key in record["subitem_seconds"]})
    count_keys = sorted({key for record in records for key in record["work_counts"]})
    columns = fixed + [f"subitem_s__{key}" for key in phase_keys] + [f"count__{key}" for key in count_keys]
    with (OUTPUT / "summary.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for record in records:
            row = {key: record.get(key) for key in fixed}
            row.update({f"subitem_s__{key}": record["subitem_seconds"].get(key) for key in phase_keys})
            row.update({f"count__{key}": record["work_counts"].get(key) for key in count_keys})
            writer.writerow(row)

    public_records = [{key: value for key, value in record.items()
                       if key not in ("resource_samples", "mps_samples")} for record in records]
    payload = {
        "units": {
            "total_and_subitem_time": "seconds",
            "cpu_peak": "percent of one logical core",
            "rss_peak": "GiB; separate from MPS",
            "mps_peaks": "MiB; allocated and driver reported separately",
            "workspace_peak": "MiB excluding source files",
            "workspace_logical_peak": "MiB including source files",
            "minimum_free_disk": "GiB",
        },
        "records": public_records,
        "excluded": excluded,
    }
    (OUTPUT / "summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"已汇总 {len(records)} 个已完成 run/case；排除 {len(excluded)} 个未完成或不可读记录。")
    print(f"输出目录：{OUTPUT}")
    for record in records:
        print(f'{record["run"]}/{record["case"]}: {record["total_s"]} 秒；样本 {record["sample_count"]}；图表 {record["chart"]}')


if __name__ == "__main__":
    main()
