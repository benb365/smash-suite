from __future__ import annotations

import csv
import json
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

from app.model_utils import model_to_dict
from app.models import (
    AnalysisResults,
    CalibrationConfig,
    KeyframeEvent,
    SessionState,
    SourceConfig,
    SpeedSample,
    TrajectoryPoint,
)


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SessionStore:
    def __init__(self, session_dir: Path, export_dir: Path) -> None:
        self.session_dir = session_dir
        self.export_dir = export_dir
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()
        self._sessions: Dict[str, SessionState] = {}
        self._results: Dict[str, AnalysisResults] = {}

    def create_session(self, name: Optional[str] = None) -> SessionState:
        session_id = uuid.uuid4().hex[:12]
        now = utc_now()
        state = SessionState(
            id=session_id,
            name=name or f"smash-{session_id[:6]}",
            status="created",
            created_at=now,
            updated_at=now,
        )
        with self._lock:
            self._sessions[session_id] = state
            self._results[session_id] = AnalysisResults(session_id=session_id)
            self._write_session(state)
            self._write_results(self._results[session_id])
        return state

    def list_sessions(self) -> List[SessionState]:
        with self._lock:
            return sorted(self._sessions.values(), key=lambda item: item.created_at, reverse=True)

    def get_session(self, session_id: str) -> SessionState:
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(session_id)
            return self._sessions[session_id]

    def get_results(self, session_id: str) -> AnalysisResults:
        with self._lock:
            if session_id not in self._results:
                raise KeyError(session_id)
            return self._results[session_id]

    def update_session(self, session_id: str, **updates: object) -> SessionState:
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(session_id)
            data = model_to_dict(self._sessions[session_id])
            data.update(updates)
            data["updated_at"] = utc_now()
            state = SessionState(**data)
            self._sessions[session_id] = state
            self._write_session(state)
            return state

    def save_calibration(self, session_id: str, calibration: CalibrationConfig) -> SessionState:
        return self.update_session(session_id, calibration=calibration, status="calibrated", error=None)

    def clear_results(self, session_id: str) -> AnalysisResults:
        with self._lock:
            if session_id not in self._sessions:
                raise KeyError(session_id)
            results = AnalysisResults(session_id=session_id)
            self._results[session_id] = results
            self._write_results(results)
            return results

    def append_trajectory(self, session_id: str, point: TrajectoryPoint) -> None:
        with self._lock:
            self._results[session_id].trajectory_points.append(point)

    def append_speed(self, session_id: str, sample: SpeedSample) -> None:
        with self._lock:
            self._results[session_id].speed_samples.append(sample)

    def append_keyframe(self, session_id: str, event: KeyframeEvent) -> None:
        with self._lock:
            self._results[session_id].keyframes.append(event)

    def finalize_results(self, session_id: str) -> AnalysisResults:
        with self._lock:
            if session_id not in self._results:
                raise KeyError(session_id)
            results = self._results[session_id]
            exports = self._write_exports(results)
            data = model_to_dict(results)
            data["exports"] = exports
            results = AnalysisResults(**data)
            self._results[session_id] = results
            self._write_results(results)
            return results

    def _session_dir(self, session_id: str) -> Path:
        path = self.session_dir / session_id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def _write_session(self, state: SessionState) -> None:
        path = self._session_dir(state.id) / "session.json"
        path.write_text(json.dumps(model_to_dict(state), indent=2), encoding="utf-8")

    def _write_results(self, results: AnalysisResults) -> None:
        path = self._session_dir(results.session_id) / "results.json"
        path.write_text(json.dumps(model_to_dict(results), indent=2), encoding="utf-8")

    def _write_exports(self, results: AnalysisResults) -> Dict[str, str]:
        export_base = self.export_dir / results.session_id
        export_base.mkdir(parents=True, exist_ok=True)
        json_path = export_base / "results.json"
        csv_path = export_base / "speed_samples.csv"

        json_path.write_text(json.dumps(model_to_dict(results), indent=2), encoding="utf-8")
        with csv_path.open("w", newline="", encoding="utf-8") as csv_file:
            writer = csv.DictWriter(
                csv_file,
                fieldnames=["time_ms", "speed_kmh", "confidence", "frame_start", "frame_end"],
            )
            writer.writeheader()
            for sample in results.speed_samples:
                writer.writerow(model_to_dict(sample))

        return {
            "json": str(json_path),
            "csv": str(csv_path),
        }
