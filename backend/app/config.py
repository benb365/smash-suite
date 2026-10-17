from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BACKEND_DIR = Path(__file__).resolve().parents[1]
PROJECT_DIR = BACKEND_DIR.parent


@dataclass(frozen=True)
class Settings:
    data_dir: Path = Path(os.getenv("SMASH_SUITE_DATA_DIR", ".runtime"))
    session_dir: Path = Path(os.getenv("SMASH_SUITE_SESSION_DIR", ".runtime/sessions"))
    export_dir: Path = Path(os.getenv("SMASH_SUITE_EXPORT_DIR", ".runtime/exports"))
    sample_dir: Path = Path(os.getenv("SMASH_SUITE_SAMPLE_DIR", PROJECT_DIR / "datasets/badminton-v1/local/test001"))
    cors_origins: tuple[str, ...] = (
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    )

    def ensure_dirs(self) -> None:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.session_dir.mkdir(parents=True, exist_ok=True)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        self.sample_dir.mkdir(parents=True, exist_ok=True)


settings = Settings()
