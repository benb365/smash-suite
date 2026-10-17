from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.dependencies import store, ws_manager
from app.model_utils import model_to_dict


router = APIRouter(tags=["websocket"])


@router.websocket("/ws/sessions/{session_id}")
async def session_socket(websocket: WebSocket, session_id: str) -> None:
    await ws_manager.connect(session_id, websocket)
    try:
        try:
            session = store.get_session(session_id)
            results = store.get_results(session_id)
            await ws_manager.send(websocket, "session_status", model_to_dict(session))
            await ws_manager.send(websocket, "analysis_results", model_to_dict(results))
        except KeyError:
            await ws_manager.send(websocket, "analysis_error", {"message": "Session not found."})

        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        ws_manager.disconnect(session_id, websocket)
