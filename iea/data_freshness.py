"""Freshness checks for economic data."""

from __future__ import annotations

import sqlite3
from datetime import datetime, timezone
from pathlib import Path


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


def check_table_freshness(
    db_path: str | Path = DEFAULT_DB,
    table_name: str = "observations",
    timestamp_column: str = "retrieved_at",
    max_age_hours: int = 48,
) -> dict:
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

        age_hours = (
            _utc_now() - latest_dt
        ).total_seconds() / 3600

        status = "ok" if age_hours <= max_age_hours else "stale"

        return {
            "status": status,
            "table": table_name,
            "latest_update": latest,
            "age_hours": round(age_hours, 2),
            "max_age_hours": max_age_hours,
        }

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
