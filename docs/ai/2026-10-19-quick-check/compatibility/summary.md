# Python 3.9 baseline audit (read-only)

Audit environment: repository `.venv` Python 3.9.6. Full references: `version-references.txt`; installed metadata: `dependency-metadata.json`.

## Shared baseline references to update if the shared interpreter changes

- `README.md:54,57` — shared Python 3.11 statement and `python3.11 -m venv` command.
- `.python-version:1` — pinned `3.11`.
- `pyproject.toml:9` — `requires-python = "==3.11.*"`; this currently rejects Python 3.9.6.
- `pyproject.toml:41` — Ruff `target-version = "py311"`.
- `modules/rally/experiments/README.md:3` and `modules/models/README.md:25` — shared Python 3.11 environment descriptions.
- `docs/assets/architecture-prompt.txt:27,56,98` — generated architecture artwork prompt labels the common environment as Python 3.11.

## Independent Python 3.10+ requirements (do not lower solely because the shared environment changes)

- `apps/android-capture/README.md:47`, `apps/android-capture/receiver/README.md:3`, `apps/android-capture/receiver/server.py:2` — standalone receiver documents/requires Python 3.10+.
- `.agents/skills/curate-badminton-training-data/SKILL.md:9`, `scripts/run.py:27,41` — the curation skill owns a Python 3.10+ environment.

## Historical environment note

- `datasets/reports/fixed-camera-rally-samples.md:75` records Python 3.10+ for that past experiment's yt-dlp environment; retain as historical evidence.

## Installed dependency metadata

The project declaration currently disallows Python 3.9, but every installed direct runtime and dev dependency's `Requires-Python` metadata permits 3.9.6. `ruff` is declared in dev dependencies but is not installed, so this environment has no metadata for it. The build-system requires `setuptools>=61`; installed setuptools is 58.0.4 (its own metadata allows 3.9, but its installed version does not satisfy the declared build requirement). No dependency was installed or changed.

## Temporary clipper work / port

`/private/tmp/smash-quick-clipper-20261019/data/work` exists and is not empty: it contains one directory, `process-38054-lvjfy49s`. Its named PID is not discoverable with `kill -0` (no signal sent). `lsof -nP -iTCP:56459 -sTCP:LISTEN` returned no listener; no service is listening on that task port. Nothing was removed and no process was stopped.
