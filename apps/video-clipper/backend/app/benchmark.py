"""Run real product HTTP sessions, preserving evidence before lease cleanup.

This module is a development tool, never a replacement inference pipeline.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import platform
import shutil
import socket
import subprocess
import sys
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[4]


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str), encoding="utf-8")


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def code_version():
    def git(*args):
        return subprocess.check_output(["git", *args], cwd=ROOT).decode().strip()
    files = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split("\0")
    hashes = {name: sha256(ROOT / name) for name in sorted(files)
              if name and (ROOT / name).is_file() and not name.startswith("docs/ai/")}
    return dict(commit=git("rev-parse", "HEAD"), status=git("status", "--short"),
                tree_sha256=hashlib.sha256(json.dumps(hashes, sort_keys=True).encode()).hexdigest(),
                file_sha256=hashes)


def environment():
    from modules.media.video import ffmpeg_exe
    import torch
    versions = {dist.metadata["Name"]: dist.version for dist in importlib.metadata.distributions()}
    automatic_pose = "cuda" if torch.cuda.is_available() and not torch.backends.mps.is_available() else "cpu"
    return dict(python=sys.version, executable=sys.executable, platform=platform.platform(),
                machine=platform.machine(), dependencies=versions, cpu_count=os.cpu_count(),
                mps_available=torch.backends.mps.is_available(), cuda_available=torch.cuda.is_available(),
                ffmpeg_executable=ffmpeg_exe(), ffmpeg_sha256=sha256(ffmpeg_exe()),
                ffmpeg_version=subprocess.check_output([ffmpeg_exe(), "-version"], text=True),
                threads=dict(worker_env={name: "1" for name in
                    ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS")},
                    torch_intraop=4, opencv=1,
                    pose_device=os.environ.get("SMASH_SUITE_POSE_DEVICE") or automatic_pose,
                    pose_batch_size=os.environ.get("SMASH_SUITE_POSE_BATCH_SIZE") or "1",
                    model_device="automatic"))


def work_bytes(directory):
    """Logical file bytes, including imported source; excludes persistent model cache."""
    total = source = 0
    for path in directory.rglob("*"):
        try:
            if path.is_file():
                size = path.stat().st_size
                total += size
                if path.name == "source.mp4":
                    source += size
        except FileNotFoundError:
            pass
    return total, total - source


class ResourceSampler:
    def __init__(self, pid, directory, destination):
        import psutil
        self.psutil, self.pid, self.directory = psutil, pid, directory
        self.destination = destination
        self.stop_event = threading.Event()
        self.processes = {}
        self.last_sample = None
        self.thread = threading.Thread(target=self.run, name="benchmark-resources", daemon=True)

    def snapshot(self):
        psutil = self.psutil
        now = time.monotonic()
        errors = []
        rows = []
        try:
            root = psutil.Process(self.pid)
            current = [root, *root.children(recursive=True)]
        except psutil.Error as exc:
            current = []
            errors.append(str(exc))
        for process in current:
            try:
                identity = (process.pid, process.create_time())
                item = self.processes.get(identity)
                if item is None:
                    process.cpu_percent(None)
                    self.processes[identity] = process
                else:
                    process = item
                cpu = process.cpu_percent(None) if item is not None else None
                rows.append(dict(pid=process.pid, parent_pid=process.ppid(), name=process.name(),
                                 created_at=identity[1], cpu_percent=cpu,
                                 cpu_seconds=sum(process.cpu_times()[:2]), rss_bytes=process.memory_info().rss))
            except psutil.Error as exc:
                errors.append(dict(pid=process.pid, error=str(exc)))
        total, without_source = work_bytes(self.directory)
        interval = None if self.last_sample is None else now - self.last_sample
        self.last_sample = now
        return dict(monotonic_s=now, interval_s=interval, processes=rows, errors=errors,
                    cpu_percent=sum(row["cpu_percent"] or 0 for row in rows),
                    rss_bytes=sum(row["rss_bytes"] for row in rows),
                    work_logical_bytes=total, work_without_source_logical_bytes=without_source,
                    disk_free_bytes=shutil.disk_usage(self.directory).free)

    def run(self):
        with self.destination.open("w", encoding="utf-8") as stream:
            while True:
                stream.write(json.dumps(self.snapshot()) + "\n")
                stream.flush()
                if self.stop_event.wait(1):
                    stream.write(json.dumps(self.snapshot()) + "\n")
                    break

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.stop_event.set()
        self.thread.join()


def summarize_resources(path):
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    return dict(samples=len(rows), max_interval_s=max((r["interval_s"] or 0 for r in rows), default=0),
                pids=sorted({p["pid"] for row in rows for p in row["processes"]}),
                observed_peak={key: max((row[key] for row in rows), default=0)
                    for key in ("cpu_percent", "rss_bytes", "work_logical_bytes", "work_without_source_logical_bytes")},
                minimum_disk_free_bytes=min((r["disk_free_bytes"] for r in rows), default=None),
                errors=[r for r in rows if r["errors"]],
                limitations="One-second observations can miss short-lived processes and transient peaks. "
                            "CPU is percent of one logical core; RSS sums processes and may count shared pages twice. "
                            "MPS counters are separate, never added to RSS.")


def request(method, url, **kwargs):
    import requests
    response = requests.request(method, url, timeout=60, **kwargs)
    response.raise_for_status()
    return response.json() if response.content else None


def keep_lease(url, token, stop, errors):
    from websockets.sync.client import connect
    try:
        with connect(url, open_timeout=10) as ws:
            ws.send(json.dumps(dict(token=token)))
            last = time.monotonic()
            while not stop.is_set():
                if time.monotonic() - last >= 10:
                    ws.send("ping")
                    last = time.monotonic()
                try:
                    ws.recv(timeout=.5)
                except TimeoutError:
                    pass
    except Exception as exc:
        if not stop.is_set():
            errors.append(str(exc))


def terminate_backend(backend):
    """Stop this runner's backend; return any unverified tree-cleanup failure."""
    if os.name != "nt":
        backend.terminate()
        return None
    # A venv redirector may own Uvicorn. Terminate only our Popen's tree.
    taskkill = Path(os.environ.get("SystemRoot") or r"C:\Windows") / "System32" / "taskkill.exe"
    try:
        subprocess.run([str(taskkill), "/PID", str(backend.pid), "/T", "/F"],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       creationflags=subprocess.CREATE_NO_WINDOW, check=True, timeout=5)
    except (OSError, subprocess.SubprocessError) as exc:
        error = f"Backend tree termination unverified: {type(exc).__name__}: {exc}"
        try:
            if backend.poll() is None:
                backend.terminate()
        except OSError as fallback:
            error += f"; backend terminate failed: {fallback}"
        return error
    return None


def run_case(case, args):
    case_dir = args.output / case["case_id"]
    case_dir.mkdir(parents=True, exist_ok=False)
    home = case_dir / "home"
    # No downloads: verify and copy the prepared cache before starting the timed job.
    from modules.rally.scenarios import required_models
    from modules.models.assets import ASSETS
    models = home / "models"
    models.mkdir(parents=True)
    weights = {}
    model_names = list(required_models(case["scene"]))
    if case["scene"] == "high" and case.get("show_shot_paths", False) and "yolo11n.pt" not in model_names:
        model_names.append("yolo11n.pt")
    for name in model_names:
        source = args.models / name
        actual = sha256(source)
        if actual != ASSETS[name]["sha256"]:
            raise ValueError(f"Prepared weight SHA mismatch: {source}")
        shutil.copy2(source, models / name)
        weights[name] = dict(source=str(source), sha256=actual)
    write_json(case_dir / "input.json", case)
    source = Path(case["video"])
    actual_sha = sha256(source)
    if actual_sha != case["sha256"]:
        raise ValueError(f"Approved video SHA mismatch: {source}")
    config = dict(profile_wait=args.profile_wait, profile_timeout_s=args.profile_timeout,
                  mps_signposts=args.mps_signposts, statistics_enabled=not args.no_statistics)
    env = dict(os.environ, PYTHONPATH=os.pathsep.join([str(ROOT), str(ROOT / "apps/video-clipper/backend")]),
               SMASH_SUITE_DATA_DIR=str(home), SMASH_SUITE_BENCHMARK_CONFIG=json.dumps(config))
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    base = f"http://127.0.0.1:{port}"
    stop = threading.Event()
    lease_errors = []
    session_url = None
    directory = None
    backend = None
    lease = None
    result = dict(case_id=case["case_id"], input=case, kind="profile" if args.profile_wait or args.mps_signposts else "baseline",
                  weights=weights, input_sha256=actual_sha, statistics_enabled=not args.no_statistics, status="failed")
    try:
        with (case_dir / "backend.log").open("w", encoding="utf-8") as log:
            backend = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1",
                                        "--port", str(port), "--log-level", "warning"],
                                       cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT,
                                       creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        deadline = time.monotonic() + 60
        while True:
            try:
                request("GET", base + "/api/health")
                break
            except Exception:
                if backend.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError("Backend startup failed; see backend.log")
                time.sleep(.1)
        session = request("POST", base + "/api/sessions")
        session_url = base + "/api/sessions/" + session["id"]
        headers = {"Authorization": "Bearer " + session["token"]}
        directory = next((home / "work").glob("process-*")) / session["id"]
        lease = threading.Thread(target=keep_lease, args=(base.replace("http:", "ws:") + "/ws/sessions/" + session["id"],
                                                        session["token"], stop, lease_errors), daemon=True)
        lease.start()
        with source.open("rb") as media:
            request("POST", session_url + "/video", headers=dict(headers, **{"X-File-Name": source.name}), data=media)
        with ResourceSampler(backend.pid, home / "work", case_dir / "resources.jsonl"):
            options = dict(camera_type=case["scene"], quality="balanced", court=case.get("court"),
                           show_shot_paths=case.get("show_shot_paths", False))
            if case.get("optimizations") is not None:
                options["optimizations"] = case["optimizations"]
            request("POST", session_url + "/run", headers=headers, json=options)
            published_ready = False
            deadline = time.monotonic() + args.timeout
            while True:
                ready_path = directory / "profile-ready.json"
                if not published_ready and ready_path.is_file():
                    ready = json.loads(ready_path.read_text(encoding="utf-8"))
                    ready.update(session_directory=str(directory), release_file=str(directory / "profile-release"))
                    if args.py_spy_path:
                        ready["py_spy_command"] = [str(args.py_spy_path), "record", "--pid", str(ready["pid"]),
                            "--output", str(case_dir / "python.speedscope.json"), "--format", "speedscope", "--rate", "100"]
                    write_json(case_dir / "profile-ready.json", ready)
                    print(json.dumps(dict(case_id=case["case_id"], event="profile_ready", **ready)), flush=True)
                    published_ready = True
                state = request("GET", session_url, headers=headers)
                if state["status"] != "running":
                    break
                if lease_errors:
                    raise RuntimeError(f"Lease connection failed: {lease_errors}")
                if time.monotonic() >= deadline:
                    raise TimeoutError("Product processing exceeded --timeout")
                time.sleep(.25)
            result["state"] = state
            if state["status"] != "completed":
                raise RuntimeError(state.get("error") or f"Job status: {state['status']}")
            # Wait for internal finally evidence after completion is published.
            while not (directory / "benchmark-clock.json").exists():
                if time.monotonic() > deadline:
                    raise TimeoutError("Missing final benchmark clock")
                time.sleep(.01)
        result["status"] = "completed"
    except Exception as exc:
        result["error"] = str(exc)
    finally:
        if directory and directory.exists():
            if result["status"] != "completed" and session_url and backend.poll() is None:
                try:
                    request("POST", session_url + "/cancel", headers=headers)
                except Exception as exc:
                    result["cancel_error"] = str(exc)
            evidence = case_dir / "evidence"
            evidence.mkdir()
            for path in directory.iterdir():
                if path.is_file() and path.name != "source.mp4":
                    shutil.copy2(path, evidence / path.name)
            result["artifacts"] = {p.name: dict(bytes=p.stat().st_size, sha256=sha256(p))
                                   for p in evidence.iterdir() if p.is_file()}
            clock_path = evidence / "benchmark-clock.json"
            if result["status"] == "completed" and clock_path.exists():
                clock = json.loads(clock_path.read_text(encoding="utf-8"))
                result["timings"] = dict(**result["state"]["timings"], total_s=result["state"]["elapsed_s"])
                result["clock"] = clock
            # Evidence is safe; the following DELETE intentionally closes the
            # WebSocket. Mark teardown first so its normal 1001 is not a lease error.
            stop.set()
            if session_url and backend.poll() is None:
                try:
                    request("DELETE", session_url, headers=headers)
                except Exception as exc:
                    result["cleanup_error"] = str(exc)
        stop.set()
        if lease:
            lease.join(3)
        if backend:
            if backend.poll() is None:
                error = terminate_backend(backend)
                if error:
                    result["cleanup_error"] = "; ".join(filter(None, (result.get("cleanup_error"), error)))
            try:
                backend.wait(timeout=10)
            except subprocess.TimeoutExpired:
                backend.kill()
                backend.wait()
            # Windows forced termination cannot run the app lifespan cleanup.
            # The authenticated session was closed above; remove only its known
            # empty process directory, never another runtime or residual data.
            if directory is not None:
                owned_process = directory.parent.resolve()
                work_root = (home / "work").resolve()
                if owned_process.parent == work_root and owned_process.name.startswith("process-"):
                    try:
                        owned_process.rmdir()
                    except FileNotFoundError:
                        pass
                    except OSError as exc:
                        result["cleanup_error"] = "; ".join(filter(None, (result.get("cleanup_error"), str(exc))))
        if (case_dir / "resources.jsonl").exists():
            result["resources"] = summarize_resources(case_dir / "resources.jsonl")
            result["resources_sha256"] = sha256(case_dir / "resources.jsonl")
        result["lease_errors"] = lease_errors
        write_json(case_dir / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--cases", nargs="+", required=True)
    parser.add_argument("--models", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--timeout", type=float, default=21600)
    parser.add_argument("--profile-wait", action="store_true")
    parser.add_argument("--profile-timeout", type=float, default=300)
    parser.add_argument("--mps-signposts", action="store_true")
    parser.add_argument("--no-statistics", action="store_true",
                        help="Disable worker aggregates only for an independent profiling run")
    parser.add_argument("--py-spy-path", type=Path)
    args = parser.parse_args(argv)
    for key in ("inputs", "models", "output", "report"):
        setattr(args, key, getattr(args, key).resolve())
    if args.no_statistics and not (args.profile_wait or args.mps_signposts):
        parser.error("--no-statistics is only allowed in profiling mode")
    if args.py_spy_path:
        version = subprocess.check_output([str(args.py_spy_path), "--version"], text=True).strip()
        if version != "py-spy 0.4.2":
            parser.error(f"Expected py-spy 0.4.2; got {version}")
        if not args.profile_wait:
            parser.error("--py-spy-path requires --profile-wait")
    payload = json.loads(args.inputs.read_text(encoding="utf-8"))
    cases = {case["case_id"]: case for case in payload["cases"]}
    selected = [cases[name] for name in args.cases]
    for case in selected:
        if case.get("status") != "passed":
            parser.error(f"Media preflight has not passed: {case['case_id']}")
    if args.report.exists():
        parser.error("Report already exists; choose a fresh path")
    args.output.mkdir(parents=True, exist_ok=False)
    write_json(args.output / "manifest.json", dict(schema_version=1, code=code_version(), environment=environment(),
        algorithm_profiles=json.loads((ROOT / "modules/rally/scenarios/profiles.json").read_text(encoding="utf-8")),
        algorithm_selection=json.loads((ROOT / "modules/rally/scenarios/selection.json").read_text(encoding="utf-8")),
        inputs_index=str(args.inputs), inputs_sha256=sha256(args.inputs), arguments=vars(args),
        protocol="Real product API, WebSocket lease, new backend and worker per case; sequential; no downloads."))
    results = []
    for case in selected:
        try:
            result = run_case(case, args)
        except Exception as exc:
            result = dict(case_id=case["case_id"], status="failed", error=str(exc), stage="preflight")
            case_dir = args.output / case["case_id"]
            case_dir.mkdir(exist_ok=True)
            write_json(case_dir / "result.json", result)
        results.append(result)
        write_json(args.output / "results.json", results)
        args.report.parent.mkdir(parents=True, exist_ok=True)
        write_json(args.report, dict(schema_version=1, status="completed" if len(results) == len(selected)
            and all(row["status"] == "completed" for row in results) else "incomplete",
            kind="profile" if args.profile_wait or args.mps_signposts else "baseline",
            evidence_directory=str(args.output), manifest_sha256=sha256(args.output / "manifest.json"),
            inputs_sha256=sha256(args.inputs), results=results,
            limits="One run per input, not a stability estimate or 30-minute acceptance. Profiling is separate from baseline."))
        if result["status"] != "completed":
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
