"""Run the separate A product-default plus shot-path overlay check."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "apps/video-clipper/backend"))
from app.benchmark import main as benchmark_main

ARGS = [
    "--inputs", str(ROOT / "docs/ai/advanced-options/show-paths-inputs.json"),
    "--cases", "A-default-show-paths",
    "--models", str(ROOT / "apps/video-clipper/.runtime/performance-first-round/combined-d/D-short/home/models"),
    "--output", str(ROOT / "apps/video-clipper/.runtime/advanced-options/20261023-native/show-paths"),
    "--report", str(ROOT / "apps/video-clipper/reports/advanced-options/show-paths-results.json"),
]

if __name__ == "__main__":
    raise SystemExit(benchmark_main([*ARGS, *sys.argv[1:]]))
