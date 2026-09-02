from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .eight_factor import analyze_eight_factor
from .health import check_all, overall_status
from .pipeline import pull_and_check


REPORT_PATH = Path("health_report.json")
MAX_PULL_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (2, 5)


def _save_report(payload: dict) -> None:
    REPORT_PATH.write_text(
        json.dumps(payload, default=str, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _pull_with_retry():
    last_error: requests.HTTPError | None = None
    for attempt in range(1, MAX_PULL_ATTEMPTS + 1):
        try:
            return pull_and_check()
        except requests.HTTPError as exc:
            last_error = exc
            if attempt == MAX_PULL_ATTEMPTS:
                raise
            time.sleep(RETRY_DELAYS_SECONDS[attempt - 1])
    raise last_error  # pragma: no cover


def run() -> int:
    started = datetime.now(timezone.utc).isoformat()
    store = None

    try:
        store, freshness_results, pipeline_status = _pull_with_retry()
        health_results = check_all(store)
        health_status = overall_status(health_results)
        intelligence = analyze_eight_factor(store)

        if pipeline_status != "OK":
            status = "error"
            exit_code = 1
        elif health_status == "HEALTHY":
            status = "ok"
            exit_code = 0
        else:
            status = "warning"
            exit_code = 0

        payload = {
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "pipeline_status": pipeline_status,
            "health_status": health_status,
            "observations": store.count(),
            "database": str(store.path),
            "freshness": freshness_results,
            "health": health_results,
            "intelligence": intelligence,
        }
        _save_report(payload)
        print(json.dumps(payload, default=str, ensure_ascii=False, indent=2))
        return exit_code
    except Exception as exc:
        payload = {
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        _save_report(payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(run())
