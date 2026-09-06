from __future__ import annotations

import logging
import os
import time
from pathlib import Path

from .scheduler import run as run_scheduler

LOGGER = logging.getLogger("iea.production_worker")
DEFAULT_INTERVAL_SECONDS = 900


def _interval_seconds() -> int:
    raw = os.getenv("IEA_SCHEDULER_INTERVAL_SECONDS", str(DEFAULT_INTERVAL_SECONDS))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("IEA_SCHEDULER_INTERVAL_SECONDS must be an integer") from exc
    if value < 60:
        raise ValueError("IEA_SCHEDULER_INTERVAL_SECONDS must be at least 60 seconds")
    return value


def _runtime_dir() -> Path:
    raw = os.getenv("IEA_RUNTIME_DIR", "/data")
    path = Path(raw)
    path.mkdir(parents=True, exist_ok=True)
    return path


def main() -> int:
    logging.basicConfig(level=os.getenv("IEA_LOG_LEVEL", "INFO"))
    runtime_dir = _runtime_dir()
    os.chdir(runtime_dir)
    interval = _interval_seconds()
    LOGGER.info("IEA production scheduler started: interval=%ss runtime=%s", interval, runtime_dir)

    while True:
        started = time.monotonic()
        try:
            exit_code = run_scheduler()
            if exit_code:
                LOGGER.error("IEA scheduler cycle completed with exit code %s", exit_code)
            else:
                LOGGER.info("IEA scheduler cycle completed successfully")
        except Exception:
            LOGGER.exception("IEA scheduler cycle crashed")

        elapsed = time.monotonic() - started
        time.sleep(max(0.0, interval - elapsed))


if __name__ == "__main__":
    raise SystemExit(main())
