from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DEFAULT_REPORT_PATH = Path("health_report.json")
DEFAULT_MAX_AGE_SECONDS = 6 * 60 * 60


def report_path(path: str | Path | None = None) -> Path:
    if path is not None:
        return Path(path)
    configured = os.getenv("IEA_REPORT_PATH", "").strip()
    return Path(configured) if configured else DEFAULT_REPORT_PATH


def _max_age_seconds() -> int:
    raw = os.getenv("IEA_REPORT_MAX_AGE_SECONDS", str(DEFAULT_MAX_AGE_SECONDS))
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError("IEA_REPORT_MAX_AGE_SECONDS must be an integer") from exc
    if value < 0:
        raise ValueError("IEA_REPORT_MAX_AGE_SECONDS must be non-negative")
    return value


def _parse_timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError("IEA report is missing finished_at")
    try:
        timestamp = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("IEA report finished_at is not a valid ISO timestamp") from exc
    if timestamp.tzinfo is None:
        timestamp = timestamp.replace(tzinfo=timezone.utc)
    return timestamp.astimezone(timezone.utc)


def load_latest_report(path: str | Path | None = None) -> dict[str, Any]:
    """Load the newest scheduler report from the configured trusted path.

    The API deliberately reads the scheduler's latest report instead of
    rerunning the data pipeline for every request. Freshness is exposed in
    the returned metadata so callers can block stale advice without hiding
    the operational state of the service.
    """
    resolved = report_path(path)
    try:
        payload = json.loads(resolved.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to load IEA report: {resolved}") from exc

    if not isinstance(payload, dict):
        raise ValueError("IEA report must contain a JSON object")
    if payload.get("status") not in {"ok", "warning"}:
        raise ValueError("IEA report is not a trusted successful report")

    finished_at = _parse_timestamp(payload.get("finished_at"))
    age_seconds = max(0.0, (datetime.now(timezone.utc) - finished_at).total_seconds())
    max_age = _max_age_seconds()
    payload["report_meta"] = {
        "path": str(resolved),
        "finished_at": finished_at.isoformat(),
        "age_seconds": round(age_seconds, 3),
        "max_age_seconds": max_age,
        "fresh": age_seconds <= max_age,
    }
    return payload
