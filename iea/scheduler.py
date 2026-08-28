"""Automation entrypoint for scheduled economic data ingestion."""

from __future__ import annotations

import json
from datetime import datetime, timezone

from .pipeline import pull


def run() -> dict:
    started = datetime.now(timezone.utc).isoformat()

    store = pull()

    payload = {
        "started_at": started,
        "finished_at": datetime.now(timezone.utc).isoformat(),
        "status": "ok",
        "database": str(getattr(store, "path", "")),
    }

    print(json.dumps(payload, default=str, indent=2))

    return payload


if __name__ == "__main__":
    run()
