"""Tab-scoped, leased workspaces. Nothing here is task history."""
from __future__ import annotations

import asyncio
import json
import os
import secrets
import shutil
import signal
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from fastapi import WebSocket

from app.product_types import JobState, ProcessingTimings, ProcessRequest
from app.runtime import Runtime


@dataclass
class Session:
    id: str
    token: str
    media_key: str
    directory: Path
    expires_at: float
    state: JobState = field(default_factory=JobState)
    socket: WebSocket | None = None
    task: asyncio.Task | None = None
    upload_task: asyncio.Task | None = None
    process: asyncio.subprocess.Process | None = None
    spawned: asyncio.Event = field(default_factory=asyncio.Event)
    closed: bool = False

    def public(self):
        return self.state.model_dump()


class Sessions:
    def __init__(self, runtime: Runtime, lease_s: float = 60):
        self.runtime = runtime
        self.lease_s = lease_s
        self.items: dict[str, Session] = {}
        self.busy: str | None = None

    def create(self) -> Session:
        sid = secrets.token_urlsafe(18)
        path = self.runtime.work / sid
        path.mkdir()
        session = Session(sid, secrets.token_urlsafe(32), secrets.token_urlsafe(32), path,
                          time.monotonic() + self.lease_s)
        self.items[sid] = session
        return session

    def authenticated(self, sid: str, token: str) -> Session | None:
        session = self.items.get(sid)
        if session and not session.closed and secrets.compare_digest(session.token, token):
            return session
        return None

    def renew(self, session: Session):
        session.expires_at = time.monotonic() + self.lease_s

    async def publish(self, session: Session, **updates):
        session.state = session.state.model_copy(update=updates)
        socket = session.socket
        if socket:
            try:
                await asyncio.wait_for(socket.send_json(session.public()), timeout=3)
            except (RuntimeError, OSError, asyncio.TimeoutError):
                if session.socket is socket:
                    session.socket = None

    async def cancel(self, session: Session):
        if session.upload_task and not session.upload_task.done():
            session.upload_task.cancel()
            await asyncio.gather(session.upload_task, return_exceptions=True)
        if session.task and not session.task.done():
            # Wait for process creation to finish before cancellation, so a
            # cancelled spawn cannot leave a live worker without its handle.
            await session.spawned.wait()
        process = session.process
        if process and process.returncode is None:
            try:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGTERM)
                else:
                    process.terminate()
            except ProcessLookupError:
                pass
            try:
                await asyncio.wait_for(process.wait(), timeout=5)
            except asyncio.TimeoutError:
                if os.name == "posix":
                    os.killpg(process.pid, signal.SIGKILL)
                else:
                    process.kill()
                await process.wait()
        if session.task and not session.task.done():
            session.task.cancel()
            await asyncio.gather(session.task, return_exceptions=True)
        if self.busy == session.id:
            self.busy = None
        session.process = None
        (session.directory / "output.mp4").unlink(missing_ok=True)
        (session.directory / "rendering.mp4").unlink(missing_ok=True)
        if not session.closed:
            await self.publish(session, status="cancelled", stage="处理已取消，可以重新开始", progress=0,
                               output_url=None, output_bytes=None, error=None)

    async def close(self, session: Session):
        session.closed = True
        await self.cancel(session)
        if session.socket:
            try:
                await session.socket.close(code=1001)
            except RuntimeError:
                pass
        self.items.pop(session.id, None)
        shutil.rmtree(session.directory, ignore_errors=True)

    async def sweep(self):
        while True:
            await asyncio.sleep(1)
            for session in list(self.items.values()):
                if session.expires_at <= time.monotonic():
                    await self.close(session)

    async def start(self, session: Session, options: ProcessRequest):
        if self.busy:
            raise ValueError("已有录像正在处理，请完成或取消后重试。")
        if not session.state.video or session.state.status not in ("ready", "failed", "cancelled", "completed"):
            raise ValueError("请先导入有效的 MP4 录像。")
        for name in ("output.mp4", "rendering.mp4", "result.json"):
            (session.directory / name).unlink(missing_ok=True)
        spec = dict(options=options.model_dump(), video=session.state.video.model_dump(),
                    directory=str(session.directory), models=str(self.runtime.models))
        if config := os.environ.get("SMASH_SUITE_BENCHMARK_CONFIG"):
            spec["benchmark"] = json.loads(config)
        (session.directory / "request.json").write_text(json.dumps(spec), encoding="utf-8")
        self.busy = session.id
        session.spawned.clear()
        session.task = asyncio.create_task(self._run(session))
        await self.publish(session, status="running", stage="正在准备处理", progress=0, error=None,
                           output_url=None, output_bytes=None, output_duration_ms=None,
                           elapsed_s=None, timings=None,
                           camera_type=options.camera_type, quality=options.quality,
                           optimizations=options.optimizations.model_copy(), warnings=[])

    async def _run(self, session: Session):
        started = time.monotonic()
        phase, phase_started = "preparation", started
        timings = {}
        benchmark_clock = dict(worker_spawn_start=started)
        benchmark_enabled = bool(os.environ.get("SMASH_SUITE_BENCHMARK_CONFIG"))
        try:
            command = ([sys.executable, "--worker"] if getattr(sys, "frozen", False)
                       else [sys.executable, "-m", "app.worker"])
            command.append(str(session.directory / "request.json"))
            with (session.directory / "worker.log").open("w") as errors:
                session.process = await asyncio.create_subprocess_exec(
                    *command, stdout=asyncio.subprocess.PIPE, stderr=errors,
                    start_new_session=os.name == "posix")
                session.spawned.set()
                while line := await session.process.stdout.readline():
                    try:
                        event = json.loads(line)
                    except (ValueError, UnicodeDecodeError):
                        errors.write(line.decode(errors="replace"))
                        continue
                    if benchmark_enabled and event.get("type") in ("profile_ready", "benchmark_start"):
                        benchmark_clock[event["type"]] = event["monotonic_s"]
                    if event.get("type") == "progress":
                        if next_phase := event.get("phase"):
                            now = time.monotonic()
                            benchmark_clock[next_phase] = now
                            timings[f"{phase}_s"] = now - phase_started
                            phase, phase_started = next_phase, now
                        await self.publish(session, stage=event["stage"], progress=event["progress"])
                code = await session.process.wait()
            result_path = session.directory / "result.json"
            if not result_path.is_file():
                raise RuntimeError(f"处理程序意外退出（{code}）。请重新开始。")
            result = json.loads(result_path.read_text())
            if code != 0 or result.get("error"):
                raise RuntimeError(result.get("error") or "视频处理失败。")
            output = session.directory / "output.mp4"
            if not output.is_file() or not output.stat().st_size:
                raise RuntimeError("没有生成可播放的成片。")
            finished = time.monotonic()
            benchmark_clock["completed"] = finished
            # One server clock covers startup/download through output readiness;
            # explicit worker boundaries keep phases independent of progress text.
            timings[f"{phase}_s"] = finished - phase_started
            await self.publish(session, status="completed", stage="成片已生成，预览后保存", progress=1,
                               output_url=f"/media/{session.media_key}/output.mp4", output_bytes=output.stat().st_size,
                               output_duration_ms=result["output_duration_ms"], rally_count=len(result["predictions"]),
                               elapsed_s=finished - started, timings=ProcessingTimings(**timings),
                               warnings=result.get("warnings", []))
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            await self.publish(session, status="failed", stage="处理未完成", error=str(exc),
                               elapsed_s=time.monotonic() - started)
        finally:
            if benchmark_enabled:
                benchmark_clock["finished"] = time.monotonic()
                (session.directory / "benchmark-clock.json").write_text(json.dumps(benchmark_clock))
            session.spawned.set()
            if self.busy == session.id:
                self.busy = None
