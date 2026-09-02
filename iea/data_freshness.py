"""Freshness checks for economic data."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


DEFAULT_DB = Path("data/iea.sqlite3")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        normalized = value.replace("Z", "+00:00")
        parsed = datetime.fromisoformat(normalized)

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        return parsed.astimezone(timezone.utc)

    except (TypeError, ValueError):
        return None


def _elapsed_calendar_aware_hours(
    start: datetime,
    end: datetime,
    closed_weekdays: Iterable[int] | None = None,
    closed_dates: Iterable[str] | None = None,
) -> float:
    """Count elapsed hours while excluding configured market-closed days."""
    if end <= start:
        return 0.0

    closed_days = set(closed_weekdays or ())
    excluded_dates = set(closed_dates or ())
    total_seconds = 0.0
    cursor = start

    while cursor < end:
        next_day = cursor.replace(
            hour=0,
            minute=0,
            second=0,
            microsecond=0,
        )
        if next_day <= cursor:
            from datetime import timedelta
            next_day += timedelta(days=1)

        segment_end = min(end, next_day)
        date_key = cursor.date().isoformat()
        if cursor.weekday() not in closed_days and date_key not in excluded_dates:
            total_seconds += (segment_end - cursor).total_seconds()

        cursor = segment_end

    return total_seconds / 3600


def check_table_freshness(
    db_path: str | Path = DEFAULT_DB,
    table_name: str = "observations",
    timestamp_column: str = "retrieved_at",
    max_age_hours: int = 48,
    closed_weekdays: Iterable[int] | None = None,
    closed_dates: Iterable[str] | None = None,
) -> dict:
    """Check freshness, optionally excluding scheduled market-closed days."""
    path = Path(db_path)

    if not path.exists():
        return {
            "status": "critical",
            "table": table_name,
            "error": "Database file does not exist.",
        }

    try:
        with sqlite3.connect(path) as conn:
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master "
                "WHERE type='table' AND name=?",
                (table_name,),
            ).fetchone()

            if not table_exists:
                return {
                    "status": "critical",
                    "table": table_name,
                    "error": "Table does not exist.",
                }

            safe_column = timestamp_column.replace('"', '""')

            latest = conn.execute(
                f'SELECT MAX("{safe_column}") FROM "{table_name}"'
            ).fetchone()[0]

        latest_dt = _parse_datetime(latest)

        if latest_dt is None:
            return {
                "status": "warning",
                "table": table_name,
                "latest_update": latest,
                "error": "No valid timestamp found.",
            }

        now = _utc_now()
        calendar_aware = bool(closed_weekdays or closed_dates)
        if calendar_aware:
            age_hours = _elapsed_calendar_aware_hours(
                latest_dt,
                now,
                closed_weekdays=closed_weekdays,
                closed_dates=closed_dates,
            )
        else:
            age_hours = (now - latest_dt).total_seconds() / 3600

        status = "ok" if age_hours <= max_age_hours else "stale"

        result = {
            "status": status,
            "table": table_name,
            "latest_update": latest,
            "age_hours": round(age_hours, 2),
            "max_age_hours": max_age_hours,
            "calendar_aware": calendar_aware,
        }
        if closed_weekdays:
            result["closed_weekdays"] = sorted(set(closed_weekdays))
        if closed_dates:
            result["closed_dates"] = sorted(set(closed_dates))
        return result

    except Exception as exc:
        return {
            "status": "critical",
            "table": table_name,
            "error": str(exc),
        }


def main() -> int:
    result = check_table_freshness()

    print(result)

    return 0 if result["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
