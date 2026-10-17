#!/usr/bin/env python3
"""Run the curator from its isolated environment, creating it when needed."""

from __future__ import annotations

import os
import hashlib
import shutil
import subprocess
import sys
from pathlib import Path


SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
VENV_DIR = SKILL_DIR / ".venv"
READY_MARKER = VENV_DIR / ".curation-ready"


def requirements_digest() -> str:
    return hashlib.sha256((SCRIPT_DIR / "requirements.txt").read_bytes()).hexdigest()


def modern_python() -> str:
    override = os.environ.get("CURATE_PYTHON")
    candidates = [override] if override else []
    candidates += [sys.executable, "python3.13", "python3.12", "python3.11", "python3.10"]
    for candidate in candidates:
        if not candidate:
            continue
        executable = shutil.which(candidate) if not Path(candidate).is_file() else candidate
        if not executable:
            continue
        result = subprocess.run(
            [executable, "-c", "import sys; raise SystemExit(sys.version_info < (3, 10))"],
            check=False,
        )
        if result.returncode == 0:
            return executable
    raise SystemExit(
        "Python 3.10+ is required. Set CURATE_PYTHON to a compatible Python executable."
    )


def main() -> None:
    venv_python = VENV_DIR / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
    if not venv_python.exists():
        subprocess.run([modern_python(), "-m", "venv", str(VENV_DIR)], check=True)
    expected_digest = requirements_digest()
    current_digest = READY_MARKER.read_text(encoding="utf-8").strip() if READY_MARKER.exists() else ""
    if current_digest != expected_digest:
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "-r", str(SCRIPT_DIR / "requirements.txt")],
            check=True,
        )
        READY_MARKER.write_text(expected_digest + "\n", encoding="utf-8")
    os.execv(str(venv_python), [str(venv_python), str(SCRIPT_DIR / "curate.py"), *sys.argv[1:]])


if __name__ == "__main__":
    main()
