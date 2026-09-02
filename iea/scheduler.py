from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .health import check_all, overall_status
from .intelligence import analyze
from .pipeline import pull_and_check


REPORT_PATH = Path("health_report.json")


def _save_report(payload: dict) -> None:
    REPORT_PATH.write_text(
        json.dumps(payload, default=str, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def run() -> int:
    started = datetime.now(timezone.utc).isoformat()
    store = None

    try:
        store, freshness_results, pipeline_status = pull_and_check()
        health_results = check_all(store)
        health_status = overall_status(health_results)
        intelligence = analyze(store)

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
        }
        _save_report(payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(run())
