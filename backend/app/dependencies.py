from __future__ import annotations

from app.config import settings
from app.session_store import SessionStore
from app.ws_manager import ConnectionManager


settings.ensure_dirs()

store = SessionStore(settings.session_dir, settings.export_dir)
ws_manager = ConnectionManager()
