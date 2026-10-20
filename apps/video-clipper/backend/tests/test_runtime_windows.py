import os
import subprocess
import sys

from app.runtime import Runtime, process_alive


def test_runtime_probe_does_not_terminate_live_process(tmp_path):
    child = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"])
    try:
        directory = tmp_path / "work" / f"process-{child.pid}-live"
        directory.mkdir(parents=True)
        runtime = Runtime(tmp_path)
        try:
            assert process_alive(child.pid)
            assert process_alive(os.getpid())
            assert child.poll() is None
            assert directory.is_dir()
        finally:
            runtime.close()
    finally:
        child.terminate()
        child.wait(timeout=5)


def test_runtime_reclaims_only_own_dead_workspaces(tmp_path):
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait(timeout=5)
    work = tmp_path / "work"
    dead = work / f"process-{child.pid}-dead"
    unknown = work / "process-not-a-pid-preserve"
    dead.mkdir(parents=True)
    unknown.mkdir()
    runtime = Runtime(tmp_path)
    try:
        assert not dead.exists()
        assert unknown.is_dir()
    finally:
        runtime.close()
