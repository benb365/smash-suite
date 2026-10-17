from __future__ import annotations

from typing import List, Optional

from fastapi import APIRouter, HTTPException

from app.dependencies import store, ws_manager
from app.model_utils import model_to_dict
from app.models import AnalysisResults, CalibrationConfig, RunRequest, SessionCreate, SessionState
from app.runner import SessionRunner
from app.vision.calibration import with_default_world_points


router = APIRouter(prefix="/api/sessions", tags=["sessions"])
runner = SessionRunner(store, ws_manager)


def _get_session_or_404(session_id: str) -> SessionState:
    try:
        return store.get_session(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Session not found.") from exc


@router.post("", response_model=SessionState)
async def create_session(payload: Optional[SessionCreate] = None) -> SessionState:
    return store.create_session(payload.name if payload else None)


@router.get("", response_model=List[SessionState])
async def list_sessions() -> List[SessionState]:
    return store.list_sessions()


@router.get("/{session_id}", response_model=SessionState)
async def get_session(session_id: str) -> SessionState:
    return _get_session_or_404(session_id)


@router.post("/{session_id}/calibration", response_model=SessionState)
async def save_calibration(session_id: str, payload: CalibrationConfig) -> SessionState:
    _get_session_or_404(session_id)
    if len(payload.image_points) < 4:
        raise HTTPException(status_code=400, detail="At least four image points are required.")
    calibration = with_default_world_points(payload)
    state = store.save_calibration(session_id, calibration)
    await ws_manager.broadcast(session_id, "session_status", model_to_dict(state))
    return state


@router.post("/{session_id}/run", response_model=SessionState)
async def run_analysis(session_id: str, payload: RunRequest) -> SessionState:
    _get_session_or_404(session_id)
    if payload.sample_stride < 1:
        raise HTTPException(status_code=400, detail="sample_stride must be >= 1.")
    if payload.source.source_type == "video_file" and not payload.source.path:
        raise HTTPException(status_code=400, detail="A local video path is required.")
    try:
        await runner.start(session_id, payload)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return store.get_session(session_id)


@router.get("/{session_id}/results", response_model=AnalysisResults)
async def get_results(session_id: str) -> AnalysisResults:
    _get_session_or_404(session_id)
    return store.get_results(session_id)
