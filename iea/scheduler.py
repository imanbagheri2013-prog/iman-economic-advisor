"""Automation entrypoint for scheduled economic data ingestion."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .pipeline import run_pipeline


def run() -> dict:
    started = datetime.now(timezone.utc).isoformat()

    result = run_pipeline()

    payload = {
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "result": result,
    }

    print(json.dumps(payload, default=str, indent=2))

    return payload


if __name__ == "__main__":
    run()
