"""Automation entrypoint for scheduled economic data ingestion."""

import json
from datetime import datetime, timezone

from .pipeline import pull_and_check


def run() -> dict:
    """Run the economic data pipeline and report its health."""
    started = datetime.now(timezone.utc).isoformat()

    store, health_results, health_status = pull_and_check()

    try:
        payload = {
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "ok",
            "health_status": health_status,
            "series_checked": len(health_results),
            "database": str(getattr(store, "path", "")),
        }

        print(
            json.dumps(
                payload,
                default=str,
                indent=2,
        )
        )

        if health_status == "CRITICAL":
            raise RuntimeError(
                "Data Health Monitor reported CRITICAL"
            )

        return payload

    finally:
        store.close()


if __name__ == "__main__":
    run()
