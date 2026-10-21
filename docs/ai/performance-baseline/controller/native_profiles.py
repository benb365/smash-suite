#!/usr/bin/env python3
"""Export and summarize completed xctrace runs for the A/C/D short profiles.

This tool never starts or stops a recording. An explicit controller completion
acknowledgement is required before it reads the native.trace bundles.
"""
from __future__ import annotations

import argparse
import collections
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parents[4]
RUNTIME = REPO_ROOT / "apps/video-clipper/.runtime/performance-baseline"
PROFILE_ROOT = RUNTIME / "profile-analysis"
CONTROLLED_STOP_BOUNDARY = RUNTIME / "cnn-window-probe/stop-boundary-check.json"
CASES = ("A", "C", "D")
TABLES = {
    "time-profile": "//trace-toc/run[@number=\"1\"]/data/table[@schema=\"time-profile\"]",
    "metal-gpu-intervals": "//trace-toc/run[@number=\"1\"]/data/table[@schema=\"metal-gpu-intervals\"]",
    "os-signpost": "//trace-toc/run[@number=\"1\"]/data/table[@schema=\"os-signpost\"]",
}
REQUIRED_COLUMNS = {
    "time-profile": {"Sample Time", "Process", "State", "Weight", "Backtrace"},
    "metal-gpu-intervals": {"Creation", "Duration", "State", "Process"},
    "os-signpost": {
        "Timestamp", "Process", "Event Type", "Signpost identifier",
        "Name", "Format String", "Subsystem", "Message",
    },
}
NULL_SENTINEL_TYPES = {"text-backtrace"}


@dataclass(frozen=True)
class XmlValue:
    tag: str
    attrs: dict[str, str]
    text: str
    children: tuple[XmlValue, ...]
    ref: str | None = None


def pack_element(element: ET.Element) -> XmlValue:
    """Copy a row node compactly; id/ref edges stay references, never XML nodes."""
    attrs = {k: v for k, v in element.attrib.items() if k not in {"id", "ref"}}
    ref = element.attrib.get("ref")
    children = []
    for child in list(element):
        if child.attrib.get("id"):
            children.append(XmlValue(child.tag, {}, "", (), child.attrib["id"]))
        elif child.attrib.get("ref"):
            children.append(XmlValue(child.tag, {}, "", (), child.attrib["ref"]))
        else:
            children.append(pack_element(child))
    return XmlValue(element.tag, attrs, (element.text or "").strip(), tuple(children), ref)


def resolve(node: XmlValue, index: dict[str, XmlValue], *, limit: int = 64) -> XmlValue:
    seen = set()
    while node.ref is not None:
        if node.ref in seen or len(seen) >= limit:
            raise ValueError(f"cyclic/deep XML ref at <{node.tag}> ref={node.ref}")
        seen.add(node.ref)
        target = index.get(node.ref)
        if target is None:
            raise KeyError(f"unresolved XML ref: <{node.tag}> ref={node.ref}")
        node = target
    return node


def resolved_children(node: XmlValue, index: dict[str, XmlValue]) -> list[XmlValue]:
    return [resolve(child, index) for child in node.children]


def child_named(node: XmlValue, tag: str, index: dict[str, XmlValue]) -> XmlValue | None:
    for child in resolved_children(node, index):
        if child.tag == tag:
            return child
    return None


def scalar(node: XmlValue | None, index: dict[str, XmlValue]) -> str | None:
    if node is None:
        return None
    node = resolve(node, index)
    if node.text:
        return node.text
    if node.attrs.get("fmt") is not None:
        return node.attrs["fmt"]
    return None


def process_pid(node: XmlValue | None, index: dict[str, XmlValue]) -> int | None:
    if node is None:
        return None
    node = resolve(node, index)
    pid = child_named(node, "pid", index)
    value = scalar(pid, index)
    if value is None:
        return None
    try:
        return int(value.replace(",", ""))
    except ValueError:
        return None


def column_value(fields: dict[str, XmlValue], name: str, index: dict[str, XmlValue]) -> str | None:
    return scalar(fields.get(name), index)


def finite_number(value: str | None) -> float | None:
    if value is None:
        return None
    try:
        number = float(value.replace(",", ""))
    except ValueError:
        return None
    return number if number == number and abs(number) != float("inf") else None


def seconds_ns(value: str | None) -> float | None:
    number = finite_number(value)
    return number / 1_000_000_000 if number is not None else None


def parse_epoch(value: str) -> float:
    """Parse an ISO-8601 timestamp; timezone-less values are rejected."""
    parsed = dt.datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        raise ValueError(f"TOC start-date must include a timezone: {value!r}")
    return parsed.timestamp()


def parse_duration_seconds(value: str | None) -> float:
    """Accept the explicit seconds representation observed in xctrace TOC."""
    if value is None:
        raise ValueError("TOC is missing run/info/summary/duration")
    match = re.fullmatch(r"\s*([0-9]+(?:\.[0-9]+)?)\s*(?:s|sec|seconds)?\s*", value, re.I)
    if not match:
        raise ValueError(f"unrecognized xctrace duration format: {value!r}")
    duration = float(match.group(1))
    if duration <= 0:
        raise ValueError(f"xctrace duration must be positive: {value!r}")
    return duration


def metadata_path(metadata: dict, key: str) -> Path:
    value = metadata.get(key)
    if not isinstance(value, str) or not value:
        raise ValueError(f"recording.json must include {key}")
    path = Path(value)
    return path if path.is_absolute() else REPO_ROOT / path


def recognition_window(metadata: dict, toc_path: Path) -> dict:
    clock_path = metadata_path(metadata, "native_benchmark_clock_path")
    if not clock_path.is_file():
        raise FileNotFoundError(f"missing benchmark clock evidence: {clock_path}")
    clock = json.loads(clock_path.read_text(encoding="utf-8"))
    if not isinstance(clock, dict) or "benchmark_start" not in clock or "rendering" not in clock:
        raise ValueError("benchmark-clock.json must include benchmark_start and rendering monotonic values")
    offset = finite_number(str(metadata.get("monotonic_to_epoch_offset_s")))
    if offset is None:
        raise ValueError("recording.json must include numeric monotonic_to_epoch_offset_s")
    start_mono = finite_number(str(clock["benchmark_start"]))
    end_mono = finite_number(str(clock["rendering"]))
    if start_mono is None or end_mono is None or end_mono <= start_mono:
        raise ValueError("benchmark clock must have finite monotonic endpoints with rendering after benchmark_start")
    toc = ET.parse(toc_path).getroot()
    start_nodes = toc.findall("./run[@number='1']/info/summary/start-date")
    duration_nodes = toc.findall("./run[@number='1']/info/summary/duration")
    if len(start_nodes) != 1 or len(duration_nodes) != 1:
        raise ValueError("expected exactly one run/info/summary start-date and duration in xctrace TOC")
    start_text = (start_nodes[0].text or "").strip()
    duration_text = (duration_nodes[0].text or duration_nodes[0].attrib.get("fmt") or "").strip()
    trace_start_epoch = parse_epoch(start_text)
    trace_duration = parse_duration_seconds(duration_text)
    start_epoch = start_mono + offset
    end_epoch = end_mono + offset
    start_s = start_epoch - trace_start_epoch
    end_s = end_epoch - trace_start_epoch
    tolerance = 0.001  # TOC start-date is recorded to millisecond precision.
    if start_s < -tolerance or end_s <= start_s or end_s > trace_duration + tolerance:
        raise ValueError(
            "mapped recognition window falls outside the trace duration; "
            "trace clock origin requires controller review"
        )
    release_epoch = finite_number(str(metadata.get("release_epoch_s")))
    result = {
            "source": str(clock_path),
        "mapping": "benchmark monotonic + recording monotonic_to_epoch_offset_s - xctrace TOC start-date epoch",
        "toc_start_date": start_text,
        "toc_start_date_precision_tolerance_seconds": tolerance,
        "trace_duration_seconds": trace_duration,
        "benchmark_start_monotonic_seconds": start_mono,
        "rendering_monotonic_seconds": end_mono,
        "start_epoch_seconds": start_epoch,
        "end_epoch_seconds": end_epoch,
        "release_epoch_seconds": release_epoch,
        "start_trace_relative_seconds": max(0.0, start_s),
        "end_trace_relative_seconds": end_s,
        "trace_duration_contains_window": end_s <= trace_duration + tolerance and start_s >= -tolerance,
    }
    return result


def schema_columns(schema: ET.Element) -> list[dict[str, str]]:
    columns = []
    for col in schema.findall("col"):
        entry = {}
        for key in ("name", "engineering-type", "mnemonic"):
            child = col.find(key)
            entry[key.replace("-", "_")] = (child.text or "").strip() if child is not None else ""
        columns.append(entry)
    return columns


def map_row(row: ET.Element, columns: list[dict[str, str]], diagnostics: dict) -> dict[str, XmlValue]:
    children = list(row)
    fields: dict[str, XmlValue] = {}
    used: set[int] = set()
    cursor = 0
    for col in columns:
        tag = col["engineering_type"]
        found = next((i for i in range(cursor, len(children)) if i not in used and children[i].tag == tag), None)
        if found is None and tag in NULL_SENTINEL_TYPES:
            found = next((i for i in range(cursor, len(children)) if i not in used and children[i].tag == "sentinel"), None)
            if found is not None:
                fields[col["name"]] = XmlValue(tag, {}, "", ())
                used.add(found)
                cursor = found + 1
                continue
        if found is None:
            diagnostics["missing_schema_fields"][col["name"]] += 1
            continue
        fields[col["name"]] = pack_element(children[found])
        used.add(found)
        cursor = found + 1
    for i, child in enumerate(children):
        if i not in used:
            diagnostics["row_fields_not_in_schema"][child.tag] += 1
    return fields


def add_ref_diagnostics(row: ET.Element, index: dict[str, XmlValue], diagnostics: dict, row_number: int) -> None:
    for element in row.iter():
        ref = element.attrib.get("ref")
        if ref and ref not in index:
            diagnostics["unresolved_refs"][f"{element.tag}:{ref}"] += 1
            if len(diagnostics["unresolved_ref_examples"]) < 20:
                diagnostics["unresolved_ref_examples"].append({"row": row_number, "field": element.tag, "ref": ref})


def weight_seconds(value: str | None) -> float | None:
    # The preflight schema shows raw weight 1000000 formatted as 1.00 ms;
    # xctrace's raw scalar is nanoseconds, not a wall-clock duration.
    return seconds_ns(value)


def frame_stack(backtrace: XmlValue | None, index: dict[str, XmlValue]) -> list[dict[str, str]]:
    if backtrace is None:
        return []
    root = resolve(backtrace, index)
    bt = child_named(root, "backtrace", index)
    if bt is None:
        return []
    frames = []
    for frame in resolved_children(bt, index):
        if frame.tag != "frame":
            continue
        binary = child_named(frame, "binary", index)
        frames.append({
            "symbol": frame.attrs.get("name", "<unknown>"),
            "binary": (binary.attrs.get("name") if binary else None) or "<unknown>",
            "binary_path": (binary.attrs.get("path") if binary else None) or "",
        })
    return frames


def top_weighted(counter: collections.Counter, limit: int = 50) -> list[dict]:
    return [{"value": key, "weight_seconds_estimate": round(value, 6)} for key, value in counter.most_common(limit)]


def top_counts(counter: collections.Counter, limit: int = 50) -> list[dict]:
    return [{"value": key, "count": value} for key, value in counter.most_common(limit)]


def value_snapshot(node: XmlValue | None, index: dict[str, XmlValue], depth: int = 0) -> dict | None:
    if node is None or depth > 4:
        return None
    node = resolve(node, index)
    return {
        "schema_value": node.tag,
        "attributes": node.attrs,
        "raw_text": node.text,
        "formatted_value": node.attrs.get("fmt"),
        "children": [value_snapshot(child, index, depth + 1) for child in node.children[:100]],
    }


def analyze_cpu(path: Path, target_pid: int, window: dict) -> dict:
    totals = collections.Counter()
    diagnostics = {
        "missing_schema_fields": collections.Counter(),
        "row_fields_not_in_schema": collections.Counter(),
        "unresolved_refs": collections.Counter(),
        "duplicate_ids": collections.Counter(),
        "unresolved_ref_examples": [],
    }
    exclusive_symbols = collections.Counter()
    exclusive_binaries = collections.Counter()
    inclusive_symbols = collections.Counter()
    all_symbol_weights = collections.Counter()
    binary_leaf = collections.Counter()
    schema = None
    index: dict[str, XmlValue] = {}
    stack: list[ET.Element] = []
    rows_total = target_rows = running_rows = 0
    first_sample = last_sample = None
    missing_pid = missing_weight = missing_stack = 0
    unknown_states = collections.Counter()
    native_examples = collections.Counter()
    sample_window = []
    window_symbol = collections.Counter()
    window_binary = collections.Counter()
    window_inclusive = collections.Counter()
    window_binary_leaf = collections.Counter()
    window_native_examples = collections.Counter()
    window_weight = 0.0
    window_running = window_rows = outside_rows = 0
    window_first = window_last = None
    for event, element in ET.iterparse(path, events=("start", "end")):
        if event == "start":
            stack.append(element)
            continue
        if element.tag == "schema":
            schema = element
        if element.attrib.get("id"):
            ident = element.attrib["id"]
            if ident in index:
                diagnostics["duplicate_ids"][ident] += 1
            index[ident] = pack_element(element)
        if element.tag == "row":
            rows_total += 1
            if schema is None:
                raise ValueError("time-profile XML row precedes schema")
            add_ref_diagnostics(element, index, diagnostics, rows_total)
            cols = schema_columns(schema)
            fields = map_row(element, cols, diagnostics)
            try:
                pid = process_pid(fields.get("Process"), index)
            except KeyError:
                pid = None
            if pid is None:
                missing_pid += 1
            elif pid == target_pid:
                target_rows += 1
                raw_time = column_value(fields, "Sample Time", index)
                sample_time = seconds_ns(raw_time)
                in_window = sample_time is not None and window["start_trace_relative_seconds"] <= sample_time <= window["end_trace_relative_seconds"]
                if in_window:
                    window_rows += 1
                    window_first = sample_time if window_first is None else min(window_first, sample_time)
                    window_last = sample_time if window_last is None else max(window_last, sample_time)
                else:
                    outside_rows += 1
                state = column_value(fields, "State", index)
                raw_weight = column_value(fields, "Weight", index)
                weight = weight_seconds(raw_weight)
                if sample_time is not None:
                    first_sample = sample_time if first_sample is None else min(first_sample, sample_time)
                    last_sample = sample_time if last_sample is None else max(last_sample, sample_time)
                if state != "Running":
                    if state: unknown_states[state] += 1
                elif weight is None:
                    missing_weight += 1
                elif weight > 0:
                    running_rows += 1
                    totals["cpu_weight_seconds_estimate"] += weight
                    try:
                        frames = frame_stack(fields.get("Backtrace"), index)
                    except (KeyError, ValueError):
                        frames = []
                    if not frames:
                        missing_stack += 1
                    else:
                        # In the observed xctrace schema the first listed frame
                        # is the sampled leaf (tagged-backtrace fmt uses leaf ← callers).
                        leaf = frames[0]
                        exclusive_symbols[leaf["symbol"]] += weight
                        leaf_binary = leaf["binary_path"] or leaf["binary"]
                        exclusive_binaries[leaf_binary] += weight
                        binary_leaf[leaf_binary] += weight
                        for symbol in {frame["symbol"] for frame in frames}:
                            inclusive_symbols[symbol] += weight
                        example_frames = {(frame["symbol"], frame["binary"]) for frame in frames
                                          if any(token in frame["symbol"] for token in ("::", "cv::", "opencv", "Metal", "MPS", "GPURegion"))}
                        for symbol_binary in example_frames:
                            native_examples[symbol_binary] += weight
                    if in_window:
                        window_running += 1
                        window_weight += weight
                        if frames:
                            leaf = frames[0]
                            window_symbol[leaf["symbol"]] += weight
                            leaf_binary = leaf["binary_path"] or leaf["binary"]
                            window_binary[leaf_binary] += weight
                            window_binary_leaf[leaf_binary] += weight
                            for symbol in {frame["symbol"] for frame in frames}:
                                window_inclusive[symbol] += weight
                            for symbol_binary in example_frames:
                                window_native_examples[symbol_binary] += weight
            if len(sample_window) < 10:
                sample_window.append({name: column_value(fields, name, index) for name in ("Sample Time", "State", "Weight")})
            if len(stack) > 1:
                stack[-2].remove(element)
            element.clear()
        stack.pop()
    if schema is None:
        raise ValueError("time-profile XML has no schema")
    if schema.attrib.get("name") != "time-profile":
        raise ValueError(f"expected time-profile schema, got {schema.attrib.get('name')!r}")
    required = REQUIRED_COLUMNS["time-profile"]
    actual = {c["name"] for c in schema_columns(schema)}
    missing = sorted(required - actual)
    if missing:
        raise ValueError(f"time-profile schema missing required columns: {missing}")
    diagnostics["missing_schema_fields"] = dict(diagnostics["missing_schema_fields"])
    diagnostics["row_fields_not_in_schema"] = dict(diagnostics["row_fields_not_in_schema"])
    diagnostics["unresolved_refs"] = dict(diagnostics["unresolved_refs"])
    diagnostics["duplicate_ids"] = dict(diagnostics.get("duplicate_ids", {}))
    result = {
        "table_schema": schema.attrib.get("name"),
        "schema_columns": schema_columns(schema),
        "rows_total": rows_total,
        "target_pid_rows": target_rows,
        "excluded_rows": rows_total - target_rows,
        "rows_with_unresolved_process_pid": missing_pid,
        "running_positive_weight_samples": running_rows,
        "running_positive_weight_seconds_cpu_estimate": round(totals["cpu_weight_seconds_estimate"], 6),
        "target_sample_time_range_s": [first_sample, last_sample],
        "running_rows_missing_weight": missing_weight,
        "running_rows_missing_backtrace": missing_stack,
        "stack_order": "The preflight xctrace tagged-backtrace fmt presents the first listed frame as the sampled leaf followed by callers (leaf ← callers).",
        "non_running_state_counts": dict(unknown_states),
        "leaf_symbol_exclusive_top50": top_weighted(exclusive_symbols),
        "leaf_binary_exclusive_top50": top_weighted(exclusive_binaries),
        "all_leaf_binary_exclusive_weight_seconds_estimate": {k: round(v, 6) for k, v in binary_leaf.most_common()},
        "inclusive_symbol_top50": top_weighted(inclusive_symbols),
        "native_symbol_examples_top50": [{"symbol": s, "binary": b, "weight_seconds_estimate": round(w, 6)} for (s, b), w in native_examples.most_common(50)],
        "sample_values": sample_window,
        "diagnostics": diagnostics,
        "interpretation": "weight is estimated CPU sample time; weights across threads may exceed wall-clock duration. Inclusive symbol weights are not additive. Symbol names containing torch are not proof of Python execution.",
        "recognition_window": {
            "trace_relative_range_s": [window["start_trace_relative_seconds"], window["end_trace_relative_seconds"]],
            "target_rows_in_window": window_rows,
            "target_rows_outside_window_or_without_timestamp": outside_rows,
            "running_positive_weight_samples": window_running,
            "running_positive_weight_seconds_cpu_estimate": round(window_weight, 6),
            "sample_time_range_s": [window_first, window_last],
            "leaf_symbol_exclusive_top50": top_weighted(window_symbol),
            "leaf_binary_exclusive_top50": top_weighted(window_binary),
            "all_leaf_binary_exclusive_weight_seconds_estimate": {k: round(v, 6) for k, v in window_binary_leaf.most_common()},
            "inclusive_symbol_top50": top_weighted(window_inclusive),
            "native_symbol_examples_top50": [{"symbol": s, "binary": b, "weight_seconds_estimate": round(w, 6)} for (s, b), w in window_native_examples.most_common(50)],
        },
        "outside_recognition_window": {
            "target_rows": outside_rows,
            "running_positive_weight_samples": running_rows - window_running,
            "running_positive_weight_seconds_cpu_estimate": round(totals["cpu_weight_seconds_estimate"] - window_weight, 6),
            "leaf_symbol_exclusive_top50": top_weighted(exclusive_symbols - window_symbol),
            "leaf_binary_exclusive_top50": top_weighted(exclusive_binaries - window_binary),
            "inclusive_symbol_top50": top_weighted(inclusive_symbols - window_inclusive),
        },
    }
    primary_fields = (
        "running_positive_weight_samples", "running_positive_weight_seconds_cpu_estimate",
        "target_sample_time_range_s", "leaf_symbol_exclusive_top50", "leaf_binary_exclusive_top50",
        "all_leaf_binary_exclusive_weight_seconds_estimate", "inclusive_symbol_top50",
        "native_symbol_examples_top50",
    )
    result["full_trace"] = {name: result[name] for name in primary_fields}
    for name in primary_fields:
        result[name] = result["recognition_window"].get(name, result["recognition_window"].get("sample_time_range_s"))
    return result


def union_intervals(intervals: Iterable[tuple[float, float]]) -> tuple[float, list[list[float]]]:
    merged: list[list[float]] = []
    for start, end in sorted(intervals):
        if end <= start:
            continue
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum(end - start for start, end in merged), merged


def analyze_gpu(path: Path, target_pid: int, window: dict) -> dict:
    diagnostics = {"missing_schema_fields": collections.Counter(), "row_fields_not_in_schema": collections.Counter(), "unresolved_refs": collections.Counter(), "duplicate_ids": collections.Counter(), "unresolved_ref_examples": []}
    index: dict[str, XmlValue] = {}; schema = None; stack = []
    total = target = missing_pid = invalid = 0
    state_counts = collections.Counter(); state_ranges = collections.defaultdict(list); active = []; all_ranges = []
    window_state_counts = collections.Counter(); window_state_ranges = collections.defaultdict(list)
    window_active = []; window_target_rows = window_outside_rows = 0
    samples = []
    for event, element in ET.iterparse(path, events=("start", "end")):
        if event == "start": stack.append(element); continue
        if element.tag == "schema": schema = element
        if element.attrib.get("id"):
            ident=element.attrib["id"]
            if ident in index: diagnostics["duplicate_ids"][ident]+=1
            index[ident]=pack_element(element)
        if element.tag == "row":
            total += 1
            if schema is None: raise ValueError("metal-gpu-intervals XML row precedes schema")
            add_ref_diagnostics(element, index, diagnostics, total)
            fields = map_row(element, schema_columns(schema), diagnostics)
            try: pid = process_pid(fields.get("Process"), index)
            except KeyError: pid = None
            if pid is None: missing_pid += 1
            elif pid == target_pid:
                target += 1
                start = seconds_ns(column_value(fields, "Creation", index))
                duration = seconds_ns(column_value(fields, "Duration", index))
                end = start + duration if start is not None and duration is not None else None
                overlaps_window = end is not None and start < window["end_trace_relative_seconds"] and end > window["start_trace_relative_seconds"]
                if overlaps_window:
                    window_target_rows += 1
                else:
                    window_outside_rows += 1
                state = column_value(fields, "State", index) or "<missing>"
                state_counts[state] += 1
                if start is None or duration is None or duration <= 0:
                    invalid += 1
                else:
                    end = start + duration
                    state_ranges[state].append((start, end)); all_ranges.append((start, end))
                    if state == "Active": active.append((start, end))
                    if overlaps_window:
                        window_state_counts[state] += 1
                        clipped = (max(start, window["start_trace_relative_seconds"]), min(end, window["end_trace_relative_seconds"]))
                        window_state_ranges[state].append(clipped)
                        if state == "Active": window_active.append(clipped)
                if len(samples) < 10:
                    samples.append({name: column_value(fields, name, index) for name in ("Creation", "Duration", "CPU to GPU Latency", "State", "Metal Device", "Label") if name in fields})
            if len(stack)>1: stack[-2].remove(element)
            element.clear()
        stack.pop()
    if schema is None: raise ValueError("metal-gpu-intervals XML has no schema")
    if schema.attrib.get("name") != "metal-gpu-intervals": raise ValueError(f"expected metal-gpu-intervals schema, got {schema.attrib.get('name')!r}")
    actual={c["name"] for c in schema_columns(schema)}
    missing=sorted(REQUIRED_COLUMNS["metal-gpu-intervals"]-actual)
    if missing: raise ValueError(f"metal-gpu-intervals schema missing required columns: {missing}")
    active_seconds, active_union = union_intervals(active)
    window_active_seconds, window_active_union = union_intervals(window_active)
    outside_active = []
    for start, end in active:
        if start < window["start_trace_relative_seconds"]:
            outside_active.append((start, min(end, window["start_trace_relative_seconds"])))
        if end > window["end_trace_relative_seconds"]:
            outside_active.append((max(start, window["end_trace_relative_seconds"]), end))
    outside_active_seconds, outside_active_union = union_intervals(outside_active)
    observation = [min(a for a,b in all_ranges), max(b for a,b in all_ranges)] if all_ranges else None
    result = {
        "table_schema": schema.attrib.get("name"), "schema_columns": schema_columns(schema), "rows_total": total, "target_pid_rows": target,
        "excluded_rows": total-target, "rows_with_unresolved_process_pid": missing_pid,
        "state_counts_target_pid": dict(state_counts), "invalid_or_nonpositive_intervals": invalid,
        "state_ranges_s": {state: [min(a for a,b in spans), max(b for a,b in spans)] for state,spans in state_ranges.items()},
        "target_observation_range_s": observation, "active_interval_count": len(active),
        "active_union_seconds": round(active_seconds, 6), "active_union_ranges_s": active_union,
        "sample_values": samples,
        "recognition_window": {
            "trace_relative_range_s": [window["start_trace_relative_seconds"], window["end_trace_relative_seconds"]],
            "target_rows_overlapping_window": window_target_rows,
            "target_rows_outside_window": window_outside_rows,
            "state_counts": dict(window_state_counts),
            "state_ranges_s": {state: [min(a for a,b in spans), max(b for a,b in spans)] for state,spans in window_state_ranges.items()},
            "active_interval_count": len(window_active),
            "active_union_seconds": round(window_active_seconds, 6),
            "active_union_ranges_s": window_active_union,
        },
        "outside_recognition_window": {
            "target_rows_without_overlap": window_outside_rows,
            "state_counts": {state: count - window_state_counts[state] for state, count in state_counts.items()},
            "active_union_seconds": round(outside_active_seconds, 6),
            "active_union_ranges_s": outside_active_union,
        },
        "diagnostics": {"missing_schema_fields":dict(diagnostics["missing_schema_fields"]),"row_fields_not_in_schema":dict(diagnostics["row_fields_not_in_schema"]),"unresolved_refs":dict(diagnostics["unresolved_refs"]),"duplicate_ids":dict(diagnostics["duplicate_ids"]),"unresolved_ref_examples":diagnostics["unresolved_ref_examples"]},
        "interpretation": "Intervals are globally unioned across queues/nesting; overlapping durations are not summed. Any observation-relative fraction must use this trace's observed range, not formal-baseline wall time or GPU utilization.",
    }
    result["full_trace"] = {
        "state_counts_target_pid": result["state_counts_target_pid"],
        "state_ranges_s": result["state_ranges_s"],
        "active_interval_count": result["active_interval_count"],
        "active_union_seconds": result["active_union_seconds"],
        "active_union_ranges_s": result["active_union_ranges_s"],
    }
    result["state_counts_target_pid"] = result["recognition_window"]["state_counts"]
    result["state_ranges_s"] = result["recognition_window"]["state_ranges_s"]
    result["active_interval_count"] = result["recognition_window"]["active_interval_count"]
    result["active_union_seconds"] = result["recognition_window"]["active_union_seconds"]
    result["active_union_ranges_s"] = result["recognition_window"]["active_union_ranges_s"]
    return result


def analyze_signposts(path: Path, target_pid: int, window: dict) -> dict:
    diagnostics = {"missing_schema_fields": collections.Counter(), "row_fields_not_in_schema": collections.Counter(), "unresolved_refs": collections.Counter(), "duplicate_ids": collections.Counter(), "unresolved_ref_examples": []}
    index: dict[str, XmlValue] = {}; schema = None; stack = []
    total = target = missing_pid = 0
    first_target_time = last_target_time = None
    names = collections.Counter(); formats = collections.Counter(); messages = collections.Counter(); subsystems = collections.Counter(); event_types = collections.Counter()
    mps_events = collections.Counter(); mps_names = collections.Counter(); mps_formats = collections.Counter(); mps_messages = collections.Counter()
    mps_window_events = collections.Counter(); mps_before_window_events = collections.Counter(); mps_after_window_events = collections.Counter()
    signpost_tail_counts = collections.Counter()
    pending = collections.defaultdict(list); paired=[]; unmatched_begin=unmatched_end=0; invalid_pairs=0; examples=[]; mps_examples=[]
    for event, element in ET.iterparse(path, events=("start", "end")):
        if event == "start": stack.append(element); continue
        if element.tag == "schema": schema = element
        if element.attrib.get("id"):
            ident=element.attrib["id"]
            if ident in index: diagnostics["duplicate_ids"][ident]+=1
            index[ident]=pack_element(element)
        if element.tag == "row":
            total += 1
            if schema is None: raise ValueError("os-signpost XML row precedes schema")
            add_ref_diagnostics(element, index, diagnostics, total)
            fields = map_row(element, schema_columns(schema), diagnostics)
            try: pid = process_pid(fields.get("Process"), index)
            except KeyError: pid = None
            if pid is None: missing_pid += 1
            elif pid == target_pid:
                target += 1
                get=lambda n: column_value(fields,n,index)
                event_time=seconds_ns(get("Timestamp")); etype=get("Event Type") or "<missing>"
                if event_time is not None:
                    first_target_time=event_time if first_target_time is None else min(first_target_time,event_time)
                    last_target_time=event_time if last_target_time is None else max(last_target_time,event_time)
                name=get("Name") or "<empty>"; fmt=get("Format String") or "<empty>"
                subsystem=get("Subsystem") or "<empty>"; category=get("Category") or "<empty>"
                message=get("Message") or "<empty>"; identifier=get("Signpost identifier") or "<empty>"
                names[name]+=1; formats[fmt]+=1; messages[message]+=1; subsystems[subsystem]+=1; event_types[etype]+=1
                if event_time is not None and event_time > window["trace_duration_seconds"]:
                    signpost_tail_counts[(etype, subsystem, name)] += 1
                if subsystem == "PyTorchMPS":
                    mps_events[etype]+=1; mps_names[name]+=1; mps_formats[fmt]+=1; mps_messages[message]+=1
                    if event_time is not None and window["start_trace_relative_seconds"] <= event_time <= window["end_trace_relative_seconds"]:
                        mps_window_events[etype] += 1
                    elif event_time is not None and event_time < window["start_trace_relative_seconds"]:
                        mps_before_window_events[etype] += 1
                    elif event_time is not None and event_time > window["end_trace_relative_seconds"]:
                        mps_after_window_events[etype] += 1
                    if len(mps_examples)<30:
                        mps_examples.append({"time_s":event_time,"event_type":etype,"name":name,"subsystem":subsystem,"category":category,"format_string":fmt,"message":message,"identifier":identifier,
                                             "actual_schema_values":{field:value_snapshot(fields.get(field),index) for field in ("Timestamp","Event Type","Signpost identifier","Name","Format String","Subsystem","Category","Message")}})
                    if event_time is not None and etype in ("Begin","End"):
                        key=(subsystem,category,name,identifier)
                        if etype=="Begin": pending[key].append(event_time)
                        else:
                            if pending[key]:
                                begin=pending[key].pop()
                                if event_time>begin: paired.append((begin,event_time,name))
                                else: invalid_pairs+=1
                            else: unmatched_end+=1
                    elif etype=="Begin": unmatched_begin+=1
                if len(examples)<30:
                    examples.append({"time_s":event_time,"event_type":etype,"name":name,"subsystem":subsystem,"category":category,"format_string":fmt,"message":message,"identifier":identifier,
                                     "actual_schema_values":{field:value_snapshot(fields.get(field),index) for field in ("Timestamp","Event Type","Signpost identifier","Name","Format String","Subsystem","Category","Message")}})
            if len(stack)>1: stack[-2].remove(element)
            element.clear()
        stack.pop()
    if schema is None: raise ValueError("os-signpost XML has no schema")
    if schema.attrib.get("name") != "os-signpost": raise ValueError(f"expected os-signpost schema, got {schema.attrib.get('name')!r}")
    actual={c["name"] for c in schema_columns(schema)}
    missing=sorted(REQUIRED_COLUMNS["os-signpost"]-actual)
    if missing: raise ValueError(f"os-signpost schema missing required columns: {missing}")
    unmatched_begin += sum(len(v) for v in pending.values())
    interval_union, interval_ranges=union_intervals((a,b) for a,b,_ in paired)
    clipped_pairs=[(max(a,window["start_trace_relative_seconds"]),min(b,window["end_trace_relative_seconds"]))
                   for a,b,_ in paired if a < window["end_trace_relative_seconds"] and b > window["start_trace_relative_seconds"]]
    window_interval_union, window_interval_ranges=union_intervals(clipped_pairs)
    before_pairs=[(a,min(b,window["start_trace_relative_seconds"])) for a,b,_ in paired if a < window["start_trace_relative_seconds"]]
    after_pairs=[(max(a,window["end_trace_relative_seconds"]),b) for a,b,_ in paired if b > window["end_trace_relative_seconds"]]
    before_interval_union,_=union_intervals(before_pairs)
    after_interval_union,_=union_intervals(after_pairs)
    return {
        "table_schema":schema.attrib.get("name"),"schema_columns":schema_columns(schema),"rows_total":total,"target_pid_rows":target,"excluded_rows":total-target,
        "target_event_time_range_s":[first_target_time,last_target_time],
        "rows_with_unresolved_process_pid":missing_pid,"event_type_counts_target_pid":dict(event_types),
        "subsystem_counts_target_pid":dict(subsystems),"top_names_target_pid":top_counts(names),
        "top_format_strings_target_pid":top_counts(formats),"top_messages_target_pid":top_counts(messages),
        "outside_toc_event_type_subsystem_name_counts":[{"count":count,"event_type":key[0],"subsystem":key[1],"name":key[2]} for key,count in signpost_tail_counts.most_common()],
        "pytorch_mps":{"subsystem_exact_match":"PyTorchMPS","event_count":sum(mps_events.values()),"event_type_counts":dict(mps_events),
            "top_names":top_counts(mps_names),"top_format_strings":top_counts(mps_formats),"top_messages":top_counts(mps_messages),
            "sample_events":mps_examples,"paired_intervals":len(paired),"invalid_interval_pairs":invalid_pairs,"unmatched_begin_or_end":unmatched_begin+unmatched_end,
            "interval_union_seconds":round(interval_union,6),"interval_union_ranges_s":interval_ranges,
            "interpretation":"Raw full-trace PyTorchMPS Begin/End union may include events beyond TOC and is diagnostic only; it is not GPU execution time."},
        "recognition_window": {
            "trace_relative_range_s": [window["start_trace_relative_seconds"], window["end_trace_relative_seconds"]],
            "pytorch_mps_event_type_counts": dict(mps_window_events),
            "pytorch_mps_event_count": sum(mps_window_events.values()),
            "pytorch_mps_paired_interval_count": len(clipped_pairs),
            "pytorch_mps_interval_union_seconds": round(window_interval_union,6),
            "pytorch_mps_interval_union_ranges_s": window_interval_ranges,
        },
        "outside_analysis_window": {
            "pytorch_mps_before_window_event_type_counts": dict(mps_before_window_events),
            "pytorch_mps_before_window_event_count": sum(mps_before_window_events.values()),
            "pytorch_mps_before_window_interval_union_seconds": round(before_interval_union,6),
            "pytorch_mps_after_window_event_type_counts": dict(mps_after_window_events),
            "pytorch_mps_after_window_event_count": sum(mps_after_window_events.values()),
            "pytorch_mps_after_window_interval_union_seconds": round(after_interval_union,6),
        },
        "sample_events":examples,
        "diagnostics":{"missing_schema_fields":dict(diagnostics["missing_schema_fields"]),"row_fields_not_in_schema":dict(diagnostics["row_fields_not_in_schema"]),"unresolved_refs":dict(diagnostics["unresolved_refs"]),"duplicate_ids":dict(diagnostics["duplicate_ids"]),"unresolved_ref_examples":diagnostics["unresolved_ref_examples"]},
    }


def hash_file(path: Path) -> dict:
    h=hashlib.sha256(); size=0
    with path.open("rb") as f:
        while True:
            block=f.read(1024*1024)
            if not block: break
            size+=len(block);h.update(block)
    return {"path":str(path),"size_bytes":size,"sha256":h.hexdigest()}


def hash_tree(root: Path) -> dict:
    files=[]
    for path in sorted(root.rglob("*"),key=lambda p:p.relative_to(root).as_posix()):
        if path.is_symlink():
            raise ValueError(f"trace bundle contains symlink; refusing to hash ambiguous target: {path}")
        if path.is_file():
            info=hash_file(path);info["relative_path"]=path.relative_to(root).as_posix();files.append(info)
    digest=hashlib.sha256()
    for item in files:
        digest.update(item["relative_path"].encode("utf-8"));digest.update(b"\0");digest.update(item["sha256"].encode("ascii"));digest.update(b"\n")
    return {"path":str(root),"file_count":len(files),"directory_sha256":digest.hexdigest(),"files":files,
            "directory_sha256_canonicalization":"SHA256 of sorted UTF-8 relative POSIX path + NUL + lowercase file SHA-256 hex + LF for each regular file."}


def export_one(xcrun: str, trace: Path, output: Path, label: str, xpath: str | None) -> dict:
    command=[xcrun,"xctrace","export","--input",str(trace)]
    if xpath is None: command.append("--toc")
    else: command.extend(["--xpath",xpath])
    command.extend(["--output",str(output)])
    log=output.with_suffix(output.suffix+".log")
    try:
        with log.open("w",encoding="utf-8") as f:
            proc=subprocess.run(command,stdout=f,stderr=subprocess.STDOUT,text=True,check=False)
        code=proc.returncode; error=None
    except OSError as exc:
        log.write_text(f"could not execute export command: {type(exc).__name__}: {exc}\n",encoding="utf-8")
        code=None; error=f"{type(exc).__name__}: {exc}"
    return {"label":label,"command":command,"returncode":code,"output":str(output),"log":str(log),"execution_error":error}


def parse_case(exports: list[dict], target_pid: int, window: dict) -> dict:
    by={Path(e["output"]).stem:Path(e["output"]) for e in exports if e["returncode"]==0}
    missing=[name for name in TABLES if name not in by]
    if missing: raise RuntimeError(f"cannot parse incomplete exports; failed/missing tables: {missing}")
    return {
        "target_pid":target_pid,
        "time_profile":analyze_cpu(by["time-profile"],target_pid,window),
        "metal_gpu_intervals":analyze_gpu(by["metal-gpu-intervals"],target_pid,window),
        "os_signpost":analyze_signposts(by["os-signpost"],target_pid,window),
    }


def validate_trace_time_origin(analysis: dict, window: dict) -> dict:
    """Keep CPU/GPU origin strict while reporting signpost coverage independently."""
    tolerance = window["toc_start_date_precision_tolerance_seconds"]
    ranges = {
        "time-profile": analysis["time_profile"]["full_trace"]["target_sample_time_range_s"],
        "metal-gpu-intervals": analysis["metal_gpu_intervals"]["target_observation_range_s"],
        "os-signpost": analysis["os_signpost"]["target_event_time_range_s"],
    }
    checked = {}
    errors = []
    for table, span in ranges.items():
        valid = span is None or (span[0] >= -tolerance and span[1] <= window["trace_duration_seconds"] + tolerance)
        overlaps = span is not None and span[0] <= window["end_trace_relative_seconds"] and span[1] >= window["start_trace_relative_seconds"]
        checked[table] = {"target_time_range_s": span, "within_toc_trace_duration": valid, "overlaps_recognition_window": overlaps}
        if not valid and table != "os-signpost":
            errors.append(f"{table} target timestamps do not fit TOC trace duration")
    signpost_span = ranges["os-signpost"]
    signpost_tail = signpost_span is not None and signpost_span[0] >= -tolerance and signpost_span[1] > window["trace_duration_seconds"] + tolerance
    signpost_other_mismatch = signpost_span is not None and not checked["os-signpost"]["within_toc_trace_duration"] and not signpost_tail
    if signpost_other_mismatch:
        errors.append("os-signpost target timestamps extend outside TOC in a way not classified as a trailing range")
    return {
        "status": "failed" if errors else "passed_with_signpost_tail" if signpost_tail else "passed",
        "tables": checked,
        "os_signpost_tail": {
            "classification": "trailing_range_beyond_toc" if signpost_tail else "none" if checked["os-signpost"]["within_toc_trace_duration"] else "unclassified_mismatch",
            "raw_target_time_range_s": signpost_span,
            "toc_duration_seconds": window["trace_duration_seconds"],
            "tail_seconds": max(0.0, signpost_span[1] - window["trace_duration_seconds"]) if signpost_span else 0.0,
            "outside_toc_event_type_subsystem_name_counts": analysis["os_signpost"]["outside_toc_event_type_subsystem_name_counts"],
            "full_event_list_path": str(Path("apps/video-clipper/.runtime/performance-baseline/profile-analysis/signpost-boundary-events.json").resolve()),
        },
        "errors": errors,
    }


def window_for_trace(metadata: dict, window_item: dict, toc_path: Path) -> dict:
    """Intersect a native window's actual trace coverage with recognition time."""
    clock_path = metadata_path(metadata, "native_benchmark_clock_path")
    clock = json.loads(clock_path.read_text(encoding="utf-8"))
    offset = finite_number(str(metadata.get("monotonic_to_epoch_offset_s")))
    start_mono = finite_number(str(clock.get("benchmark_start")))
    end_mono = finite_number(str(clock.get("rendering")))
    ready_mono = finite_number(str(window_item.get("ready_monotonic_s")))
    if offset is None or start_mono is None or end_mono is None or ready_mono is None or end_mono <= start_mono:
        raise ValueError("recording/benchmark clock has invalid recognition endpoints")
    toc = ET.parse(toc_path).getroot()
    start_nodes = toc.findall("./run[@number='1']/info/summary/start-date")
    duration_nodes = toc.findall("./run[@number='1']/info/summary/duration")
    if len(start_nodes) != 1 or len(duration_nodes) != 1:
        raise ValueError("expected exactly one run/info/summary start-date and duration in xctrace TOC")
    trace_start_text = (start_nodes[0].text or "").strip()
    trace_start_epoch = parse_epoch(trace_start_text)
    trace_duration = parse_duration_seconds((duration_nodes[0].text or duration_nodes[0].attrib.get("fmt") or "").strip())
    trace_end_epoch = trace_start_epoch + trace_duration
    benchmark_start_epoch = start_mono + offset
    benchmark_end_epoch = end_mono + offset
    ready_epoch = ready_mono + offset
    overlap_start = max(trace_start_epoch, benchmark_start_epoch, ready_epoch)
    overlap_end = min(trace_end_epoch, benchmark_end_epoch)
    if overlap_end <= overlap_start:
        raise ValueError("native window trace coverage does not overlap benchmark_start-to-rendering interval")
    precision = 0.001
    mapped_stage_times = {}
    for key in ("trigger_observed_monotonic_s", "attach_requested_monotonic_s", "ready_monotonic_s", "completed_monotonic_s"):
        value = finite_number(str(window_item.get(key)))
        if value is None:
            raise ValueError(f"native_windows[{window_item.get('name')}] missing finite {key}")
        epoch = value + offset
        mapped_stage_times[key] = {
            "monotonic_seconds": value,
            "epoch_seconds": epoch,
            "trace_relative_seconds": epoch - trace_start_epoch,
            "covered_by_trace": trace_start_epoch - precision <= epoch <= trace_end_epoch + precision,
        }
    return {
        "name": window_item.get("name"),
        "stage": window_item.get("stage"),
        "trace_path": window_item.get("trace_path"),
        "trace_duration_seconds": trace_duration,
        "trace_start_date": trace_start_text,
        "trace_coverage_epoch_seconds": [trace_start_epoch, trace_end_epoch],
        "benchmark_recognition_epoch_seconds": [benchmark_start_epoch, benchmark_end_epoch],
        "ready_marker_monotonic_seconds": ready_mono,
        "ready_marker_epoch_seconds": ready_epoch,
        "ready_marker_trace_relative_seconds": ready_epoch - trace_start_epoch,
        "ready_marker_in_trace": trace_start_epoch - precision <= ready_epoch <= trace_end_epoch + precision,
        "ready_marker_observation_interval_seconds": 0.1,
        "ready_marker_timing_interpretation": "ready_monotonic_s is the observed marker on a 0.1 s polling loop; the actual transition may precede it by up to one polling interval. The deterministic analysis start uses the observed marker.",
        "mapped_benchmark_start_trace_relative_seconds": benchmark_start_epoch - trace_start_epoch,
        "mapped_rendering_trace_relative_seconds": benchmark_end_epoch - trace_start_epoch,
        "analysis_window_trace_relative_seconds": [overlap_start - trace_start_epoch, overlap_end - trace_start_epoch],
        "analysis_window_epoch_seconds": [overlap_start, overlap_end],
        "analysis_window_duration_seconds": overlap_end - overlap_start,
        "pre_ready_trace_period_seconds": [0.0, min(trace_duration, max(0.0, ready_epoch - trace_start_epoch))],
        "trace_covers_full_benchmark_interval": trace_start_epoch <= benchmark_start_epoch + precision and trace_end_epoch >= benchmark_end_epoch - precision,
        "toc_start_date_precision_tolerance_seconds": precision,
        "stage_clock_points": mapped_stage_times,
        "mapping": "trace TOC start-date and duration define actual trace coverage; intersect that interval with benchmark_start-to-rendering after monotonic-to-epoch mapping",
    }


def validate_stage_window(metadata: dict, mapped: dict) -> dict:
    events_path = metadata_path(metadata, "stage_events_path")
    current_path = metadata_path(metadata, "stage_current_path")
    if not events_path.is_file() or not current_path.is_file():
        raise FileNotFoundError(f"stage evidence missing: {events_path} / {current_path}")
    events = []
    with events_path.open(encoding="utf-8") as f:
        for line_number, line in enumerate(f, 1):
            if not line.strip():
                continue
            try:
                item = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid stage event JSON at line {line_number}: {exc}") from exc
            events.append(item)
    current = json.loads(current_path.read_text(encoding="utf-8"))
    def validate_event(item: dict, label: str) -> dict:
        if not isinstance(item, dict):
            raise ValueError(f"{label} must be an object")
        time = finite_number(str(item.get("monotonic_s")))
        if time is None or not isinstance(item.get("status"), str) or not isinstance(item.get("stage"), str):
            raise ValueError(f"{label} must include monotonic_s, status, and stage")
        progress = finite_number(str(item.get("progress")))
        if progress is None:
            raise ValueError(f"{label} must include numeric progress")
        return {"monotonic_s": time, "status": item["status"], "stage": item["stage"], "progress": progress}
    checked = [validate_event(event, f"stage-events.jsonl line {i}") for i, event in enumerate(events, 1)]
    current_event = validate_event(current, "stage-current.json")
    if checked and current_event["monotonic_s"] >= checked[-1]["monotonic_s"]:
        if current_event != checked[-1]:
            checked.append(current_event)
    elif not checked:
        checked.append(current_event)
    if any(b["monotonic_s"] < a["monotonic_s"] for a, b in zip(checked, checked[1:])):
        raise ValueError("stage-events.jsonl is not monotonic ordered")
    offset = finite_number(str(metadata.get("monotonic_to_epoch_offset_s")))
    if offset is None:
        raise ValueError("recording.json must include monotonic_to_epoch_offset_s")
    trace_start_epoch, trace_end_epoch = mapped["trace_coverage_epoch_seconds"]
    start = trace_start_epoch - offset
    end = trace_end_epoch - offset
    analysis_start = mapped["analysis_window_epoch_seconds"][0] - offset
    analysis_end = mapped["analysis_window_epoch_seconds"][1] - offset
    before = [event for event in checked if event["monotonic_s"] <= start]
    if not before:
        raise ValueError("stage event evidence has no state at the beginning of native trace coverage")
    state = before[-1]
    cursor = start
    segments = []
    for event in checked:
        t = event["monotonic_s"]
        if t <= start:
            continue
        if t >= end:
            break
        if t > cursor:
            segments.append({"start_monotonic_s": cursor, "end_monotonic_s": t, "status": state["status"],
                             "stage": state["stage"], "progress": state["progress"]})
        state = event
        cursor = t
    if cursor < end:
        segments.append({"start_monotonic_s": cursor, "end_monotonic_s": end, "status": state["status"],
                         "stage": state["stage"], "progress": state["progress"],
                         "closed_by_completed_job": any(e["status"].lower() == "completed" and e["monotonic_s"] >= end for e in checked)})
    selected_stage = mapped["stage"]
    in_analysis = []
    for segment in segments:
        a = max(analysis_start, segment["start_monotonic_s"])
        b = min(analysis_end, segment["end_monotonic_s"])
        if b > a:
            in_analysis.append({"start_monotonic_s": a, "end_monotonic_s": b, "status": segment["status"],
                                "stage": segment["stage"], "progress": segment["progress"]})
    observed_stages = list(dict.fromkeys(x["stage"] for x in in_analysis))
    mismatch = any(stage != selected_stage for stage in observed_stages)
    return {"events_path": str(events_path), "current_path": str(current_path), "selected_stage": selected_stage,
            "actual_stage_segments_over_trace": segments, "actual_stage_segments_over_analysis_window": in_analysis,
            "observed_stages_in_analysis_window": observed_stages,
            "crosses_selected_stage_boundary": mismatch,
            "status": "crosses-stage-boundary" if mismatch else "stage-matches-window",
            "policy": "Trace coverage is converted from epoch to monotonic using the recording offset; phase state comes only from stage-events/current evidence."}


def run_windows(args: argparse.Namespace, run_id: str) -> int:
    if "A" in args.cases:
        print("--windows is reserved for C/D phase windows; A was already analyzed as a full native capture", file=sys.stderr)
        return 2
    if args.reuse_from is not None and len(args.cases) != 1:
        print("with --windows --reuse-from, process one case at a time and pass that case's prior run directory", file=sys.stderr)
        return 2
    xcrun = shutil.which("xcrun") if args.reuse_from is None else None
    if args.reuse_from is None and xcrun is None:
        print("xcrun not found", file=sys.stderr)
        return 2
    reuse_root = args.reuse_from.resolve() if args.reuse_from else None
    failed = False
    for case in args.cases:
        control = RUNTIME / f"profile-control-{case}"
        recording = control / "recording.json"
        try:
            metadata = json.loads(recording.read_text(encoding="utf-8"))
            if not isinstance(metadata, dict):
                raise ValueError("recording.json root must be an object")
            pid = int(metadata["target_pid"])
            uid = int(metadata["target_uid"])
            if pid <= 0:
                raise ValueError(f"target_pid must be positive: {pid}")
            if uid == 0 or uid != os.getuid():
                raise ValueError(f"target_uid must be the current non-root user ({os.getuid()}): {uid}")
            for key in ("runner_returncode", "py_spy_returncode"):
                if metadata.get(key) != 0:
                    raise ValueError(f"recording.json {key} must be zero before analysis: {metadata.get(key)!r}")
            native_case_directory = metadata_path(metadata, "native_case_directory")
            windows = metadata.get("native_windows")
            if not isinstance(windows, list) or not windows:
                raise ValueError("recording.json native_windows must be a nonempty array")
            if not native_case_directory.is_dir():
                raise FileNotFoundError(f"native case directory not found: {native_case_directory}")
        except Exception as exc:
            print(f"{case}: {type(exc).__name__}: {exc}", file=sys.stderr)
            failed = True
            continue
        names = [item.get("name") for item in windows if isinstance(item, dict)]
        if len(names) != len(windows) or len(set(names)) != len(names) or any(n not in {"observation", "pose"} for n in names):
            print(f"{case}: invalid/duplicate native_windows names: {names}", file=sys.stderr)
            failed = True
            continue
        required_names = {"observation"} if case == "C" else {"observation", "pose"}
        if set(names) != required_names:
            print(f"{case}: native_windows must contain exactly {sorted(required_names)}; got {sorted(names)}", file=sys.stderr)
            failed = True
            continue
        for item in windows:
            name = item["name"]
            base = PROFILE_ROOT / case / run_id
            outdir = base / name
            try:
                outdir.mkdir(parents=True, exist_ok=False)
            except FileExistsError:
                print(f"{case}/{name}: output exists; refusing to overwrite: {outdir}", file=sys.stderr)
                failed = True
                continue
            summary = {"case_id": case, "window_name": name, "status": "failed", "errors": [], "exports": [],
                       "target_pid": pid, "target_uid": uid, "stage": item.get("stage"), "native_window_metadata": item,
                       "python_capture": metadata.get("python_capture"), "native_case_directory": str(native_case_directory)}
            status_path = outdir / "export-status.json"
            exports = []
            source_dir = (reuse_root / name) if reuse_root else None
            try:
                trace_value = item.get("trace_path")
                if not isinstance(trace_value, str) or not trace_value:
                    raise ValueError(f"native_windows[{name}] missing trace_path")
                trace_path = Path(trace_value)
                if not trace_path.is_absolute(): trace_path = REPO_ROOT / trace_path
                if not trace_path.is_dir(): raise FileNotFoundError(f"completed trace bundle not found: {trace_path}")
                if item.get("trace_returncode") != 0: raise ValueError(f"native window trace_returncode is not zero: {item.get('trace_returncode')!r}")
                if source_dir:
                    status_path = source_dir / "export-status.json"
                    if not status_path.is_file(): raise FileNotFoundError(f"reused window exports missing: {status_path}")
                    exports = json.loads(status_path.read_text(encoding="utf-8"))
                else:
                    exports = []
                    toc_path = outdir / "toc.xml"
                    exports.append(export_one(xcrun, trace_path, toc_path, "toc", None))
                    (outdir / "export-status.json").write_text(json.dumps(exports, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
                    for table, xpath in TABLES.items():
                        exports.append(export_one(xcrun, trace_path, outdir / f"{table}.xml", table, xpath))
                        (outdir / "export-status.json").write_text(json.dumps(exports, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
                    status_path = outdir / "export-status.json"
                required_labels = {"toc", *TABLES}
                if {e.get("label") for e in exports} != required_labels or any(e.get("returncode") != 0 for e in exports):
                    raise RuntimeError(f"window exports are incomplete or failed: {status_path}")
                missing_files = [e.get("output") for e in exports if not Path(e["output"]).is_file()]
                if missing_files: raise FileNotFoundError(f"window export files missing: {missing_files}")
                toc_path = Path(next(e["output"] for e in exports if e["label"] == "toc"))
                mapped = window_for_trace(metadata, item, toc_path)
                stage_validation = validate_stage_window(metadata, mapped)
                full_toc_mapped = dict(mapped)
                full_toc_mapped["analysis_window_epoch_seconds"] = mapped["trace_coverage_epoch_seconds"]
                full_toc_mapped["analysis_window_trace_relative_seconds"] = [0.0, mapped["trace_duration_seconds"]]
                full_toc_stage_validation = validate_stage_window(metadata, full_toc_mapped)
                window = {"start_trace_relative_seconds": mapped["analysis_window_trace_relative_seconds"][0],
                          "end_trace_relative_seconds": mapped["analysis_window_trace_relative_seconds"][1],
                          "trace_duration_seconds": mapped["trace_duration_seconds"],
                          "toc_start_date_precision_tolerance_seconds": mapped["toc_start_date_precision_tolerance_seconds"]}
                analysis = parse_case(exports, pid, window)
                validation = validate_trace_time_origin(analysis, window)
                summary.update({"trace_path": str(trace_path), "window_mapping": mapped, "stage_validation": stage_validation,
                                "full_toc_stage_validation": full_toc_stage_validation, "analysis": analysis,
                                "trace_time_origin_validation": validation, "exports": exports})
                summary["errors"].extend(validation["errors"])
                if validation["status"] == "passed_with_signpost_tail":
                    if name != "observation":
                        summary["errors"].append("controlled signpost-tail classification is authorized only for observation windows")
                    else:
                        if not CONTROLLED_STOP_BOUNDARY.is_file():
                            summary["errors"].append(f"controlled stop-boundary evidence is missing: {CONTROLLED_STOP_BOUNDARY}")
                        else:
                            controlled = json.loads(CONTROLLED_STOP_BOUNDARY.read_text(encoding="utf-8"))
                            real_case = controlled.get("real_windows", {}).get(f"{case}-observation")
                            actual = validation["os_signpost_tail"]
                            if controlled.get("status") != "observed_cross_table_stop_boundary_difference" or not isinstance(real_case, dict):
                                summary["errors"].append("controlled stop-boundary evidence does not report the expected observation")
                            elif abs(float(real_case.get("toc_duration_s", -1)) - window["trace_duration_seconds"]) > 1e-6 or abs(float(real_case.get("signpost_end_s", -1)) - actual["raw_target_time_range_s"][1]) > 1e-6:
                                summary["errors"].append("controlled stop-boundary evidence does not match this trace's TOC/signpost endpoint")
                            else:
                                summary["signpost_cross_table_stop_boundary"] = "reproduced_in_controlled_probe"
                                summary["controlled_stop_boundary_evidence"] = {
                                    "path": str(CONTROLLED_STOP_BOUNDARY),
                                    "sha256": hash_file(CONTROLLED_STOP_BOUNDARY)["sha256"],
                                    "status": controlled["status"],
                                    "matching_case_evidence": real_case,
                                }
                                boundary_index = Path("apps/video-clipper/.runtime/performance-baseline/profile-analysis/signpost-boundary-events.json").resolve()
                                if not boundary_index.is_file():
                                    summary["errors"].append(f"complete signpost boundary event list is missing: {boundary_index}")
                                else:
                                    summary["signpost_boundary_event_index"] = hash_file(boundary_index)
                if stage_validation["crosses_selected_stage_boundary"]:
                    summary["errors"].append("native trace overlaps stage(s) other than the selected phase; inspect stage_validation")
                cpu_nonempty = analysis["time_profile"]["recognition_window"]["running_positive_weight_samples"] > 0
                gpu_nonempty = analysis["metal_gpu_intervals"]["recognition_window"]["active_interval_count"] > 0
                mps_nonempty = analysis["os_signpost"]["recognition_window"]["pytorch_mps_event_count"] > 0
                if name == "observation" and not (cpu_nonempty and gpu_nonempty and mps_nonempty):
                    summary["errors"].append("observation window requires nonempty target CPU, GPU Active, and PyTorchMPS evidence")
                if name == "pose" and not cpu_nonempty:
                    summary["errors"].append("pose window requires target CPU evidence")
                if name == "pose" and not gpu_nonempty and not mps_nonempty:
                    summary["gpu_mps_interpretation"] = "No GPU Active intervals or PyTorchMPS signposts in pose window; treat as CPU model path only if stage evidence confirms pose stage."
                ref_problems = {n: a["diagnostics"] for n, a in analysis.items()
                                if isinstance(a, dict) and a.get("diagnostics")
                                and (a["diagnostics"]["unresolved_refs"] or a["diagnostics"].get("duplicate_ids"))}
                if ref_problems: summary["errors"].append("unresolved/duplicate XML id/ref values require inspection")
                if item.get("trace_returncode") != 0: summary["errors"].append("native trace failed")
                if summary["errors"]:
                    summary["status"] = "failed"
                elif validation["status"] == "passed_with_signpost_tail":
                    summary["status"] = "passed_with_signpost_tail"
                else:
                    summary["status"] = "passed"
            except Exception as exc:
                summary["errors"].append(f"{type(exc).__name__}: {exc}")
                exports = summary.get("exports", [])
            (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            try:
                if source_dir:
                    prior = json.loads((source_dir / "artifact-index.json").read_text(encoding="utf-8"))
                    trace_record = prior.get("trace_bundle") or {}
                    trace_index = {"path": trace_record.get("path"), "file_count": trace_record.get("file_count"),
                                   "directory_sha256": trace_record.get("directory_sha256"),
                                   "manifest_path": str(source_dir / "artifact-index.json"),
                                   "manifest_sha256": hash_file(source_dir / "artifact-index.json")["sha256"]}
                    exports_index = {"source_artifact_index": str(source_dir / "artifact-index.json"), "files": prior.get("exports_and_logs", [])}
                else:
                    trace_index = hash_tree(Path(summary["trace_path"])) if summary.get("trace_path") else None
                    exports_index = [hash_file(Path(e[k])) for e in exports for k in ("output", "log") if Path(e[k]).is_file()]
                (outdir / "artifact-index.json").write_text(json.dumps({
                    "case_id": case, "window_name": name, "stage": item.get("stage"),
                    "trace_bundle": trace_index, "exports_and_logs": exports_index,
                    "export_status": hash_file(status_path) if status_path.is_file() else None,
                    "stage_events": hash_file(metadata_path(metadata,"stage_events_path")),
                    "stage_current": hash_file(metadata_path(metadata,"stage_current_path")),
                    "summary_path": str(outdir / "summary.json"),
                    "summary_sha256": hash_file(outdir / "summary.json")["sha256"],
                    "controlled_stop_boundary_evidence": summary.get("controlled_stop_boundary_evidence"),
                    "signpost_boundary_event_index": summary.get("signpost_boundary_event_index"),
                }, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            except Exception as exc:
                summary["errors"].append(f"artifact indexing {type(exc).__name__}: {exc}")
                summary["status"] = "failed"
                (outdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2)+"\n", encoding="utf-8")
            print(f"{case}/{name}: {summary['status']} ({outdir / 'summary.json'})")
            failed |= summary["status"] not in {"passed", "passed_with_signpost_tail"}
    return 1 if failed else 0


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--controller-confirmed-complete",action="store_true",help="controller confirms all native.trace bundles are stopped and fully saved")
    parser.add_argument("--cases",nargs="+",choices=CASES,default=list(CASES))
    parser.add_argument("--run-id",help="unique output subdirectory name; defaults to UTC timestamp")
    parser.add_argument("--reuse-from",type=Path,help="re-parse an existing case output directory without re-exporting or copying its XML")
    parser.add_argument("--windows",action="store_true",help="process each recording.json native_windows entry as an independent trace")
    args=parser.parse_args()
    if not args.controller_confirmed_complete:
        parser.error("refusing to inspect/export a possibly active recording; pass --controller-confirmed-complete only after controller confirmation")
    if len(set(args.cases)) != len(args.cases):
        parser.error("--cases must not contain duplicates")
    reuse_dir = args.reuse_from.resolve() if args.reuse_from else None
    if reuse_dir is not None and len(args.cases) != 1:
        parser.error("--reuse-from accepts exactly one case")
    if reuse_dir is not None:
        required = ("observation",) if args.cases[0] == "C" else ("observation", "pose")
        if args.windows:
            missing = [str(reuse_dir / window / name) for window in required
                       for name in ("export-status.json", "artifact-index.json")
                       if not (reuse_dir / window / name).is_file()]
            if missing:
                parser.error(f"--reuse-from is missing window export artifacts: {missing}")
        else:
            for name in ("export-status.json", "artifact-index.json"):
                if not (reuse_dir / name).is_file():
                    parser.error(f"--reuse-from is missing {name}: {reuse_dir / name}")
    run_id=args.run_id or dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
    if run_id in {".", ".."} or not re.fullmatch(r"[A-Za-z0-9_.-]{1,80}", run_id):
        parser.error("--run-id must be a single safe path component (letters, digits, dot, underscore, hyphen)")
    if args.windows:
        return run_windows(args,run_id)
    xcrun=shutil.which("xcrun") if reuse_dir is None else None
    if reuse_dir is None and xcrun is None:
        print("xcrun not found",file=sys.stderr);return 2
    failed=False
    for case in args.cases:
        control=RUNTIME/f"profile-control-{case}"
        trace=control/"native.trace"; recording=control/"recording.json"
        outdir=PROFILE_ROOT/case/run_id
        try:
            outdir.mkdir(parents=True,exist_ok=False)
        except FileExistsError:
            print(f"{case}: output already exists; refusing to overwrite: {outdir}",file=sys.stderr)
            failed=True
            continue
        result={"case_id":case,"output_directory":str(outdir),"status":"failed","exports":[],"errors":[]}
        try:
            if not recording.is_file(): raise FileNotFoundError(f"missing recording metadata: {recording}")
            metadata=json.loads(recording.read_text(encoding="utf-8"))
            if not isinstance(metadata,dict): raise ValueError("recording.json root must be an object")
            if "target_pid" not in metadata or "target_uid" not in metadata:
                raise ValueError("recording.json must include target_pid and target_uid")
            pid=int(metadata["target_pid"]);uid=int(metadata["target_uid"])
            if pid<=0 or uid<0: raise ValueError("recording target_pid/target_uid must be nonnegative identifiers")
            native_case_directory=metadata_path(metadata,"native_case_directory")
            capture=metadata.get("python_capture")
            if not isinstance(capture,dict) or not isinstance(capture.get("flamegraph"),str):
                raise ValueError("recording.json python_capture must include the original flamegraph path")
            flame_value=Path(capture["flamegraph"])
            flame=flame_value if flame_value.is_absolute() else REPO_ROOT/flame_value
            if not trace.is_dir(): raise FileNotFoundError(f"completed trace bundle not found: {trace}")
            if not native_case_directory.is_dir(): raise FileNotFoundError(f"native case directory not found: {native_case_directory}")
            if not flame.is_file(): raise FileNotFoundError(f"raw py-spy flamegraph not found: {flame}")
            result["recording_metadata"]=metadata
            result["target_pid"]=pid;result["target_uid"]=uid
            result["native_case_directory"]=str(native_case_directory)
            result["trace_path"]=str(trace);result["python_flamegraph_path"]=str(flame)
            exports=[]
            result["exports"]=exports
            export_status_path=(reuse_dir if reuse_dir is not None else outdir)/"export-status.json"
            if reuse_dir is not None:
                exports=json.loads(export_status_path.read_text(encoding="utf-8"))
                if not isinstance(exports,list) or any(e.get("returncode") != 0 for e in exports):
                    raise ValueError(f"reused exports are incomplete or failed: {export_status_path}")
                result["reused_exports_from"]=str(reuse_dir)
            else:
                toc=outdir/"toc.xml"
                exports.append(export_one(xcrun,trace,toc,"toc",None))
                export_status_path.write_text(json.dumps(exports,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                for table,xpath in TABLES.items():
                    exports.append(export_one(xcrun,trace,outdir/f"{table}.xml",table,xpath))
                    export_status_path.write_text(json.dumps(exports,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
            result["exports"]=exports
            export_failures=[e for e in exports if e["returncode"]!=0]
            if export_failures:
                result["errors"].append(f"{len(export_failures)} xctrace export command(s) failed")
            else:
                required_export_labels={"toc",*TABLES}
                labels={e.get("label") for e in exports}
                if labels != required_export_labels:
                    raise ValueError(f"expected exports {sorted(required_export_labels)}, got {sorted(str(x) for x in labels)}")
                missing_files=[e.get("output") for e in exports if not Path(e["output"]).is_file()]
                if missing_files:
                    raise FileNotFoundError(f"reused/exported XML files are missing: {missing_files}")
                toc=Path(next(e["output"] for e in exports if e["label"]=="toc"))
                window=recognition_window(metadata,toc)
                result["recognition_window"]=window
                analysis=parse_case(exports,pid,window)
                result["analysis"]=analysis
                origin_validation=validate_trace_time_origin(analysis,window)
                result["trace_time_origin_validation"]=origin_validation
                result["errors"].extend(origin_validation["errors"])
                evidence_nonempty={
                    "time_profile":analysis["time_profile"]["target_pid_rows"]>0 and analysis["time_profile"]["running_positive_weight_samples"]>analysis["time_profile"]["running_rows_missing_backtrace"],
                    "metal_gpu_intervals":analysis["metal_gpu_intervals"]["target_pid_rows"]>0 and analysis["metal_gpu_intervals"]["active_interval_count"]>0,
                    "os_signpost":analysis["os_signpost"]["target_pid_rows"]>0,
                }
                result["required_target_evidence_nonempty"]=evidence_nonempty
                if not all(evidence_nonempty.values()):
                    result["errors"].append("one or more required target-PID evidence sets are empty")
                cpu_window=analysis["time_profile"]["recognition_window"]
                gpu_window=analysis["metal_gpu_intervals"]["recognition_window"]
                if cpu_window["target_rows_in_window"] == 0 or cpu_window["running_positive_weight_samples"] == 0:
                    result["errors"].append("no target CPU samples fall inside the mapped recognition window")
                if gpu_window["active_interval_count"] == 0:
                    result["errors"].append("no target Active GPU intervals overlap the mapped recognition window")
                ref_problems={name:analysis[name]["diagnostics"] for name in ("time_profile","metal_gpu_intervals","os_signpost") if analysis[name]["diagnostics"]["unresolved_refs"] or analysis[name]["diagnostics"].get("duplicate_ids")}
                result["reference_diagnostics_clear"]=not ref_problems
                if ref_problems: result["errors"].append("unresolved or duplicate XML id/ref values require inspection: "+json.dumps(ref_problems,ensure_ascii=False))
                if analysis["os_signpost"]["pytorch_mps"]["event_count"]==0:
                    result["warnings"]=["no target-PID subsystem=PyTorchMPS signpost rows were exported"]
            result["status"]="passed" if not result["errors"] else "failed"
        except Exception as exc:
            result["errors"].append(f"{type(exc).__name__}: {exc}")
        summary_path=outdir/"summary.json"
        summary_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        try:
            if reuse_dir is not None:
                source_index_path=reuse_dir/"artifact-index.json"
                source_index=json.loads(source_index_path.read_text(encoding="utf-8"))
                trace_source=source_index.get("trace_bundle") or {}
                exports_source=source_index.get("exports_and_logs") or []
                python_source=source_index.get("python_flamegraph")
                trace_manifest={"path":trace_source.get("path"),"file_count":trace_source.get("file_count"),
                                "directory_sha256":trace_source.get("directory_sha256"),
                                "manifest_path":str(source_index_path),"manifest_sha256":hash_file(source_index_path)["sha256"]}
                artifact_exports={"source_artifact_index":str(source_index_path),"files":exports_source}
            else:
                trace_manifest=hash_tree(trace) if trace.is_dir() else None
                python_source=hash_file(flame) if flame.is_file() else None
                artifact_exports= [hash_file(Path(e[k])) for e in result["exports"] for k in ("output","log") if Path(e[k]).is_file()]
            artifacts={
                "case_id":case,"recording_metadata":result.get("recording_metadata"),
                "trace_bundle":trace_manifest,
                "python_flamegraph":python_source,
                "exports_and_logs":artifact_exports,
                "export_status":hash_file(export_status_path) if export_status_path.is_file() else None,
                "summary_path":str(summary_path),
                "summary_sha256":hash_file(summary_path)["sha256"],
            }
            (outdir/"artifact-index.json").write_text(json.dumps(artifacts,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        except Exception as exc:
            result["errors"].append(f"artifact indexing {type(exc).__name__}: {exc}")
            result["status"]="failed"
            summary_path.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(f"{case}: {result['status']} ({summary_path})")
        failed |= result["status"]!="passed"
    return 1 if failed else 0


if __name__=="__main__":
    raise SystemExit(main())
