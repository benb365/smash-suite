"""Locations owned by the installed application, independent of the checkout."""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


def process_alive(pid: int) -> bool:
    if os.name == "nt":
        # os.kill(pid, 0) can terminate the target process on Windows.
        # Query an existing process handle instead; do not signal it.
        import ctypes
        from ctypes import wintypes
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel.OpenProcess.argtypes = (wintypes.DWORD, wintypes.BOOL, wintypes.DWORD)
        kernel.OpenProcess.restype = wintypes.HANDLE
        kernel.GetExitCodeProcess.argtypes = (wintypes.HANDLE, ctypes.POINTER(wintypes.DWORD))
        kernel.CloseHandle.argtypes = (wintypes.HANDLE,)
        handle = kernel.OpenProcess(0x1000, False, pid)
        if not handle:
            return ctypes.get_last_error() != 87  # Invalid PID; access denied stays live.
        try:
            code = wintypes.DWORD()
            return not kernel.GetExitCodeProcess(handle, ctypes.byref(code)) or code.value == 259
        finally:
            kernel.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True


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
                if not process_alive(pid):
                    shutil.rmtree(path, ignore_errors=True)
            except (ValueError, PermissionError):
                continue
        self.work = Path(tempfile.mkdtemp(prefix=f"process-{os.getpid()}-", dir=self.work_root))

    def close(self):
        shutil.rmtree(self.work, ignore_errors=True)
