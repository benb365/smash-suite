"""Locations owned by the installed application, independent of the checkout."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


def app_home() -> Path:
    override = os.environ.get("SMASH_SUITE_DATA_DIR")
    if override:
        return Path(override).expanduser().resolve()
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "SmashSuite"
    if sys.platform == "win32":
        return Path(os.environ.get("LOCALAPPDATA", Path.home())) / "SmashSuite"
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local/share")) / "smash-suite"


def web_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "web"
    return Path(__file__).resolve().parents[2] / "frontend" / "dist"


class Runtime:
    def __init__(self, home: Path | None = None):
        self.home = home or app_home()
        self.models = self.home / "models"
        self.work_root = self.home / "work"
        self.models.mkdir(parents=True, exist_ok=True)
        self.work_root.mkdir(parents=True, exist_ok=True)
        # Only reclaim this application's dead process directories. Another
        # running instance and all model caches are deliberately excluded.
        for path in self.work_root.glob("process-*-*"):
            try:
                pid = int(path.name.split("-")[1])
                os.kill(pid, 0)
            except ProcessLookupError:
                shutil.rmtree(path, ignore_errors=True)
            except (ValueError, PermissionError):
                continue
        self.work = Path(tempfile.mkdtemp(prefix=f"process-{os.getpid()}-", dir=self.work_root))

    def close(self):
        shutil.rmtree(self.work, ignore_errors=True)
