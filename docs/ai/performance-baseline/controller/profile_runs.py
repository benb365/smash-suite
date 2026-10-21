"""Approved C/D full Python captures and 8-second native phase windows.

Application/algorithm code stays frozen. Native window validity requires the
trace TOC and exported samples, not an inference from these request clocks.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shlex
import signal
import subprocess
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[4]
RUNTIME = ROOT / "apps/video-clipper/.runtime/performance-baseline"
PYTHON = ROOT / ".venv/bin/python"
SPY = Path("/private/tmp/smash-performance-tools/bin/py-spy")
CASES = ("C-short", "D-short")
STAGES = {"observation": "正在寻找羽毛球和球员", "pose": "正在分析球员动作"}
SETTLE_SECONDS = 4
WINDOW_SECONDS = 8


def save(path, data):
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(path)


class Recording:
    """Serialize main-loop and background trace-save updates to one evidence file."""
    def __init__(self, path, data):
        self.path, self.data = path, data
        self.lock = threading.Lock()
        self.update()

    def update(self, **values):
        with self.lock:
            self.data.update(values)
            save(self.path, self.data)

    def add_window(self, window):
        with self.lock:
            self.data["native_windows"].append(copy.deepcopy(window))
            save(self.path, self.data)

    def window(self, name, **values):
        with self.lock:
            item = next(w for w in self.data["native_windows"] if w["name"] == name)
            item.update(values)
            save(self.path, self.data)

    def diagnostic(self, message, **context):
        with self.lock:
            self.data["diagnostics"].append(dict(monotonic_s=time.monotonic(), message=message, **context))
            save(self.path, self.data)

    def snapshot(self):
        with self.lock:
            return copy.deepcopy(self.data)


class StageObserver:
    """Observe the original request return; never record credentials or headers."""
    def __init__(self, request, controls):
        self.request, self.controls = request, controls
        self.previous = None

    def __call__(self, method, url, **kwargs):
        result = self.request(method, url, **kwargs)
        if method.upper() == "GET" and isinstance(result, dict) and "status" in result and "stage" in result:
            state = dict(monotonic_s=time.monotonic(), status=result["status"],
                         stage=result["stage"], progress=result["progress"])
            save(self.controls / "stage-current.json", state)
            identity = (state["status"], state["stage"])
            if identity != self.previous:
                with (self.controls / "stage-events.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(state, ensure_ascii=False) + "\n")
                self.previous = identity
        return result


class StageGate:
    def __init__(self, stage):
        self.stage, self.since = stage, None
        self.first_state = None

    def eligible(self, state, now):
        if not state or state["status"] != "running" or state["stage"] != self.stage:
            self.since = None
            self.first_state = None
            return False
        if self.since is None:
            self.since = state["monotonic_s"]
            self.first_state = copy.deepcopy(state)
        # A stale HTTP snapshot is not confirmation that the worker is still in
        # that stage. Normal benchmark polling is every quarter second.
        return now - self.since >= SETTLE_SECONDS and now - state["monotonic_s"] <= 2


def read_stage(path):
    return json.loads(path.read_text()) if path.exists() else None


def wait_for(predicate, processes, seconds=240):
    deadline = time.monotonic() + seconds
    while not predicate():
        if any(p.poll() is not None for p in processes):
            raise RuntimeError("Required process ended before attachment readiness")
        if time.monotonic() > deadline:
            raise TimeoutError("Sampler attachment timed out")
        time.sleep(.1)


def runner_mode(argv):
    parser = argparse.ArgumentParser(description="Observe the existing benchmark HTTP state")
    parser.add_argument("--controls", type=Path, required=True)
    parser.add_argument("benchmark_args", nargs=argparse.REMAINDER)
    args = parser.parse_args(argv)
    passed = args.benchmark_args
    if passed[:1] == ["--"]:
        passed = passed[1:]
    selection = argparse.ArgumentParser(add_help=False)
    selection.add_argument("--cases", nargs=1, choices=CASES, required=True)
    selected, _ = selection.parse_known_args(passed)
    if selected.cases[0] not in CASES:
        parser.error("Only C-short or D-short is authorized")
    from app import benchmark
    original = benchmark.request
    benchmark.request = StageObserver(original, args.controls.resolve())
    try:
        return benchmark.main(passed)
    finally:
        benchmark.request = original


def trace_command(pid, path):
    return ["xcrun", "xctrace", "record", "--template", "Time Profiler", "--instrument", "GPU",
            "--instrument", "os_signpost", "--attach", str(pid), "--time-limit", "8s", "--output", str(path)]


def complete_window(process, log, name, recording):
    try:
        code = process.wait(timeout=1800)
        recording.window(name, trace_returncode=code, completed_monotonic_s=time.monotonic())
        if code != 0:
            recording.diagnostic("Native trace recording/save failed", window=name, trace_returncode=code)
    except Exception as exc:
        recording.window(name, completed_monotonic_s=time.monotonic(), save_error=str(exc))
        recording.diagnostic("Native trace save did not complete", window=name, error=str(exc))
    finally:
        log.close()


def observe_window(window, state, now, recording):
    """Stage changes are evidence, not permission to silently retry a window."""
    if not state or state["monotonic_s"] < window["attach_requested_monotonic_s"]:
        return
    endpoint = window.get("ready_monotonic_s")
    if endpoint is not None and state["monotonic_s"] > endpoint + WINDOW_SECONDS:
        return  # Later save time is not attributed to the requested capture.
    previous = window["stage_observations"][-1] if window["stage_observations"] else None
    if previous and previous["monotonic_s"] == state["monotonic_s"]:
        return
    observations = window["stage_observations"] + [state]
    window["stage_observations"] = observations
    recording.window(window["name"], stage_observations=observations)
    changed = state["status"] != "running" or state["stage"] != window["stage"]
    if changed and not window.get("stage_change_diagnosed"):
        window["stage_change_diagnosed"] = True
        recording.window(window["name"], stage_change_diagnosed=True)
        recording.diagnostic("Stage changed during native attachment/requested window; TOC verification required",
                             window=window["name"], observed_state=state, detected_monotonic_s=now)


def start_window(name, state, pid, controls, recording, *, trigger_state=None, popen=None):
    popen = popen or subprocess.Popen
    trigger_state = trigger_state or state
    requested = time.monotonic()
    path = controls / (name + ".trace")
    command = trace_command(pid, path)
    window = dict(name=name, stage=STAGES[name], trace_path=str(path), trace_command=command,
                  trace_log_path=str(controls / (name + "-xctrace.log")), requested_duration_s=WINDOW_SECONDS,
                  trigger_observed_monotonic_s=trigger_state["monotonic_s"], attach_requested_monotonic_s=requested,
                  ready_monotonic_s=None, completed_monotonic_s=None, trace_returncode=None,
                  trigger_state=trigger_state, attach_state=state, stage_observations=[state], coverage_status="pending_trace_TOC_and_phase_validation")
    recording.add_window(window)
    log = Path(window["trace_log_path"]).open("w")
    try:
        process = popen(command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
    except Exception:
        log.close()
        raise
    recording.window(name, trace_pid=process.pid)
    return window, process, log


def terminate_application(runner):
    """Only the still-identifiable ordinary-UID subtree of this invocation."""
    import psutil
    if runner.poll() is not None:
        return
    try:
        root = psutil.Process(runner.pid)
        if root.uids().real != os.getuid() or os.getuid() == 0:
            return
        children = root.children(recursive=True)
        owned = []
        for child in reversed(children):
            try:
                if child.uids().real == os.getuid():
                    child.terminate()
                    owned.append(child)
            except psutil.Error:
                pass
        root.terminate()
        owned.append(root)
        _, alive = psutil.wait_procs(owned, timeout=5)
        for process in alive:
            try:
                process.kill()
            except psutil.Error:
                pass
    except psutil.Error:
        pass


def run(case):
    if case not in CASES or os.getuid() == 0:
        raise ValueError("Explicit C-short/D-short and an ordinary application UID are required")
    folder = RUNTIME / ("profile-" + case[0])
    report = ROOT / "apps/video-clipper/reports" / ("performance-profile-" + case[0] + ".json")
    controls = RUNTIME / ("profile-control-" + case[0])
    if folder.exists() or report.exists():
        raise FileExistsError("Existing profile evidence must not be overwritten")
    controls.mkdir(exist_ok=False)
    events = dict(case_id=case, application_uid=os.getuid(), native_windows=[], diagnostics=[],
                  stage_events_path=str(controls / "stage-events.jsonl"),
                  stage_current_path=str(controls / "stage-current.json"),
                  native_case_directory=str(folder / case),
                  native_benchmark_clock_path=str(folder / case / "evidence/benchmark-clock.json"),
                  capture_scope="Full Python capture; native 8-second selected-stage windows only",
                  native_clock_note="completed_monotonic_s includes trace save; actual sampling interval must come from trace TOC",
                  python_capture=dict(case_directory=str(folder / case), flamegraph=str(controls / "python-flamegraph.svg")),
                  status="preparing")
    recording = Recording(controls / "recording.json", events)
    benchmark_args = ["--inputs", str(RUNTIME / "media/inputs.json"), "--cases", case,
        "--models", str(RUNTIME / "prepared-models"), "--output", str(folder), "--report", str(report),
        "--profile-wait", "--profile-timeout", "300", "--mps-signposts", "--no-statistics", "--py-spy-path", str(SPY)]
    command = [str(PYTHON), str(Path(__file__).resolve()), "--runner", "--controls", str(controls), "--", *benchmark_args]
    recording.update(runner_command=command)
    runner = spy = None
    windows, waiters = [], []
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "apps/video-clipper/backend")]))
    try:
        with (controls / "runner.log").open("w") as log:
            runner = subprocess.Popen(command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT)
        recording.update(runner_pid=runner.pid)
        ready_file = folder / case / "profile-ready.json"
        wait_for(ready_file.exists, [runner], 120)
        ready = json.loads(ready_file.read_text())
        pid = ready["pid"]
        import psutil
        target = psutil.Process(pid)
        def target_alive():
            try:
                return target.is_running() and target.status() != psutil.STATUS_ZOMBIE
            except psutil.Error:
                return False
        uid = target.uids().real
        if uid != os.getuid() or uid == 0:
            raise RuntimeError("Target worker is not the ordinary calling UID")
        recording.update(target_pid=pid, target_uid=uid,
                         python_capture=dict(target_pid=pid, case_directory=str(folder / case),
                                             flamegraph=str(controls / "python-flamegraph.svg")))
        spy_log_path = controls / "py-spy.log"
        spy_command = [str(SPY), "record", "--pid", str(pid), "--output", str(controls / "python-flamegraph.svg"),
                       "--format", "flamegraph", "--rate", "100"]
        shell = shlex.join(spy_command) + " > " + shlex.quote(str(spy_log_path)) + " 2>&1"
        authorization = "do shell script " + json.dumps(shell) + " with administrator privileges"
        recording.update(py_spy_command=spy_command)
        with (controls / "sampler-authorization.log").open("w") as log:
            spy = subprocess.Popen(["/usr/bin/osascript", "-e", authorization], stdout=log, stderr=subprocess.STDOUT)
        print(json.dumps(dict(case=case, event="waiting_for_python_sampler", pid=pid)), flush=True)
        wait_for(lambda: spy_log_path.exists() and "Sampling process" in spy_log_path.read_text(errors="replace"),
                 [runner, spy])
        python_ready = time.monotonic()
        release = time.monotonic()
        offset = time.time() - time.monotonic()
        recording.update(python_ready_monotonic_s=python_ready, samplers_ready_monotonic_s=python_ready,
                         release_monotonic_s=release, release_epoch_s=release + offset,
                         monotonic_to_epoch_offset_s=offset, status="running")
        Path(ready["release_file"]).touch()
        required = ["observation"] + (["pose"] if case == "D-short" else [])
        gates = {name: StageGate(STAGES[name]) for name in required}
        state_path = Path(events["stage_current_path"])
        deadline = time.monotonic() + 21600
        while runner.poll() is None:
            now = time.monotonic()
            if now > deadline:
                raise TimeoutError("Full benchmark runner exceeded six hours")
            state = read_stage(state_path)
            # Readiness is the validated xctrace attachment marker; the actual
            # capture interval will still be taken from the exported trace TOC.
            for window, process, _ in windows:
                log_text = Path(window["trace_log_path"]).read_text(errors="replace")
                if window["ready_monotonic_s"] is None and "Ctrl-C to stop the recording" in log_text:
                    window["ready_monotonic_s"] = now
                    recording.window(window["name"], ready_monotonic_s=now)
                observe_window(window, state, now, recording)
            pending = [name for name in required if name not in {w[0]["name"] for w in windows}]
            previous_saved = not windows or windows[-1][1].poll() is not None
            if pending and previous_saved:
                name = pending[0]
                if gates[name].eligible(state, now):
                    # Re-read the newest atomically published GET snapshot just
                    # before attach; no inferred progress fraction is used.
                    confirmed = read_stage(state_path)
                    if gates[name].eligible(confirmed, time.monotonic()) and target_alive():
                        window, process, log = start_window(name, confirmed, pid, controls, recording,
                                                            trigger_state=gates[name].first_state)
                        windows.append((window, process, log))
                        waiter = threading.Thread(target=complete_window,
                            args=(process, log, name, recording), name="save-" + name, daemon=True)
                        waiter.start()
                        waiters.append(waiter)
            if spy.poll() is not None and (spy.returncode != 0 or target_alive()):
                raise RuntimeError("Python sampler ended before its target worker")
            time.sleep(.1)
        recording.update(runner_returncode=runner.returncode, runner_done_monotonic_s=time.monotonic())
        for waiter in waiters:
            waiter.join(1801)
            if waiter.is_alive():
                recording.diagnostic("Native save waiter still running")
        recording.update(py_spy_returncode=spy.wait(timeout=60))
        captured = {window["name"] for window, _, _ in windows}
        for name in required:
            if name not in captured:
                recording.diagnostic("Required stage was not captured before the application exited", window=name, stage=STAGES[name])
        for window in recording.snapshot()["native_windows"]:
            if window["ready_monotonic_s"] is None:
                recording.diagnostic("Native window never reported attachment readiness", window=window["name"])
            if window["trace_returncode"] != 0 or not Path(window["trace_path"]).is_dir():
                recording.diagnostic("Native trace missing or save failed", window=window["name"])
        if runner.returncode != 0 or spy.returncode != 0 or recording.snapshot()["diagnostics"]:
            raise RuntimeError("Profiling control failed; retain recording.json and per-window logs")
        recording.update(status="recorded_pending_TOC_and_sample_validation")
        print(json.dumps(dict(case=case, event="phase_windows_saved", native_windows=required)), flush=True)
    except BaseException as exc:
        recording.diagnostic("Controller stopped", error=str(exc), error_type=type(exc).__name__)
        recording.update(status="failed")
        raise
    finally:
        if runner is not None:
            terminate_application(runner)
            recording.update(runner_returncode=runner.poll())
        for window, process, _ in windows:
            if process.poll() is None:
                process.send_signal(signal.SIGINT)
        if spy is not None:
            try:
                recording.update(py_spy_returncode=spy.wait(timeout=10))
            except subprocess.TimeoutExpired:
                # Only terminate our ordinary osascript wrapper. The elevated
                # sampler is not selected by name or broadly killed.
                spy.terminate()
                recording.diagnostic("Sampler wrapper did not exit after the application subtree stopped")


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["--runner"]:
        return runner_mode(argv[1:])
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("cases", nargs="+", choices=CASES, help="Explicit C-short and/or D-short only; A history is preserved")
    args = parser.parse_args(argv)
    for case in args.cases:
        run(case)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
