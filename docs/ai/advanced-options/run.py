"""Run the eight approved real-product optimization cases sequentially."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/video-clipper/backend"))
from app.benchmark import main as benchmark_main

CASES = [
    "A-all-off", "C-all-off", "D-all-off",
    "A-new-default", "C-new-default", "D-new-default",
    "C-dynamic-on", "D-dynamic-on",
]
ARGS = [
    "--inputs", str(ROOT / "docs/ai/advanced-options/inputs.json"),
    "--cases", *CASES,
    "--models", str(ROOT / "apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models"),
    "--output", str(ROOT / "apps/video-clipper/.runtime/advanced-options/20261023-native"),
    "--report", str(ROOT / "apps/video-clipper/reports/advanced-options/results-native.json"),
]

if __name__ == "__main__":
    raise SystemExit(benchmark_main([*ARGS, *sys.argv[1:]]))
