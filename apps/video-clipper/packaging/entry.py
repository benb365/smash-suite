"""Standalone application entrypoint, including spawned analysis workers."""
import multiprocessing

from app.__main__ import main

if __name__ == "__main__":
    multiprocessing.freeze_support()
    raise SystemExit(main())
