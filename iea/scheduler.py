from __future__ import annotations

import json
from datetime import datetime, timezone

from .health import check_all, overall_status
from .pipeline import pull_and_check


def run() -> int:
    started = datetime.now(timezone.utc).isoformat()
    store = None

    try:
        store, freshness_results, pipeline_status = pull_and_check()
        health_results = check_all(store)
        health_status = overall_status(health_results)
        status = "ok" if pipeline_status == "OK" and health_status == "HEALTHY" else "warning"

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
        }
        print(json.dumps(payload, default=str, indent=2))
        return 0 if status == "ok" else 1
    except Exception as exc:
        payload = {
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error_type": type(exc).__name__,
        }
        print(json.dumps(payload, indent=2))
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(run())
