from __future__ import annotations

from typing import Any, Dict, Set

from fastapi import WebSocket
from fastapi.encoders import jsonable_encoder


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: Dict[str, Set[WebSocket]] = {}

    async def connect(self, session_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.setdefault(session_id, set()).add(websocket)

    def disconnect(self, session_id: str, websocket: WebSocket) -> None:
        sockets = self._connections.get(session_id)
        if not sockets:
            return
        sockets.discard(websocket)
        if not sockets:
            self._connections.pop(session_id, None)

    async def send(self, websocket: WebSocket, event_type: str, payload: Any) -> None:
        await websocket.send_json(jsonable_encoder({"type": event_type, "payload": payload}))

    async def broadcast(self, session_id: str, event_type: str, payload: Any) -> None:
        sockets = list(self._connections.get(session_id, set()))
        for websocket in sockets:
            try:
                await self.send(websocket, event_type, payload)
            except RuntimeError:
                self.disconnect(session_id, websocket)
