from __future__ import annotations

import asyncio
from typing import Dict

from app.model_utils import model_to_dict
from app.models import KeyframeEvent, RunRequest, SpeedSample, TrajectoryPoint
from app.session_store import SessionStore
from app.vision.pipeline import analyze_source
from app.ws_manager import ConnectionManager


class SessionRunner:
    def __init__(self, store: SessionStore, ws_manager: ConnectionManager) -> None:
        self.store = store
        self.ws_manager = ws_manager
        self._tasks: Dict[str, asyncio.Task[None]] = {}

    def is_running(self, session_id: str) -> bool:
        task = self._tasks.get(session_id)
        return task is not None and not task.done()

    async def start(self, session_id: str, request: RunRequest) -> None:
        if self.is_running(session_id):
            raise RuntimeError("Session is already running.")
        session = self.store.get_session(session_id)
        if session.calibration is None:
            raise RuntimeError("Calibration is required before running analysis.")

        self.store.clear_results(session_id)
        state = self.store.update_session(
            session_id,
            status="running",
            source=request.source,
            latest_speed_kmh=None,
            result_count=0,
            error=None,
        )
        await self.ws_manager.broadcast(session_id, "session_status", model_to_dict(state))
        self._tasks[session_id] = asyncio.create_task(self._run(session_id, request))

    async def _run(self, session_id: str, request: RunRequest) -> None:
        try:
            session = self.store.get_session(session_id)
            assert session.calibration is not None
            async for event in analyze_source(session_id, request, session.calibration):
                event_type = event["type"]
                payload = event["payload"]
                await self._handle_event(session_id, event_type, payload)

            results = self.store.finalize_results(session_id)
            latest_speed = results.speed_samples[-1].speed_kmh if results.speed_samples else None
            state = self.store.update_session(
                session_id,
                status="completed",
                latest_speed_kmh=latest_speed,
                result_count=len(results.speed_samples),
                error=None,
            )
            await self.ws_manager.broadcast(session_id, "session_status", model_to_dict(state))
            await self.ws_manager.broadcast(session_id, "analysis_complete", model_to_dict(results))
        except Exception as exc:  # noqa: BLE001
            state = self.store.update_session(session_id, status="failed", error=str(exc))
            await self.ws_manager.broadcast(session_id, "analysis_error", {"message": str(exc)})
            await self.ws_manager.broadcast(session_id, "session_status", model_to_dict(state))

    async def _handle_event(self, session_id: str, event_type: str, payload: object) -> None:
        if event_type == "trajectory_point":
            point = payload if isinstance(payload, TrajectoryPoint) else TrajectoryPoint(**payload)
            self.store.append_trajectory(session_id, point)
            await self.ws_manager.broadcast(session_id, event_type, model_to_dict(point))
            return

        if event_type == "speed_sample":
            sample = payload if isinstance(payload, SpeedSample) else SpeedSample(**payload)
            self.store.append_speed(session_id, sample)
            self.store.update_session(
                session_id,
                latest_speed_kmh=sample.speed_kmh,
                result_count=self.store.get_session(session_id).result_count + 1,
            )
            await self.ws_manager.broadcast(session_id, event_type, model_to_dict(sample))
            return

        if event_type == "keyframe_event":
            keyframe = payload if isinstance(payload, KeyframeEvent) else KeyframeEvent(**payload)
            self.store.append_keyframe(session_id, keyframe)
            await self.ws_manager.broadcast(session_id, event_type, model_to_dict(keyframe))
            return

        await self.ws_manager.broadcast(session_id, event_type, model_to_dict(payload))
