from datetime import date, datetime, timezone
from typing import Any

from .storage import Store


def _days_since(value: str | None) -> int | None:
    """Return the number of UTC days since an ISO date/datetime."""
    if not value:
        return None

    try:
        parsed = datetime.fromisoformat(
            value.replace("Z", "+00:00")
        )

        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)

        now = datetime.now(timezone.utc)
        return max(0, (now - parsed).days)

    except ValueError:
        try:
            parsed_date = date.fromisoformat(value)
            return max(0, (date.today() - parsed_date).days)
        except ValueError:
            return None


def _status(
    record_count: int,
    missing_count: int,
    latest_date: str | None,
    freshness_days: int | None,
) -> str:
    """Calculate a simple health status for a series."""

    if record_count == 0:
        return "CRITICAL"

    if missing_count > 0:
        return "WARNING"

    if latest_date is None:
        return "WARNING"

    if freshness_days is not None and freshness_days > 365:
        return "CRITICAL"

    if freshness_days is not None and freshness_days > 90:
        return "WARNING"

    return "HEALTHY"


def check_series(
    store: Store,
    provider: str,
    series_id: str,
) -> dict[str, Any]:
    """
    Check the health of a single provider/series combination.
    """

    row = store.con.execute(
        """
        SELECT
            COUNT(*) AS record_count,
            SUM(
                CASE
                    WHEN value IS NULL THEN 1
                    ELSE 0
                END
            ) AS missing_count,
            MAX(date) AS latest_date,
            MAX(retrieved_at) AS last_retrieved_at
        FROM observations
        WHERE provider = ?
          AND series_id = ?
        """,
        (provider, series_id),
    ).fetchone()

    record_count = int(row[0] or 0)
    missing_count = int(row[1] or 0)
    latest_date = row[2]
    last_retrieved_at = row[3]

    freshness_days = _days_since(latest_date)

    status = _status(
        record_count=record_count,
        missing_count=missing_count,
        latest_date=latest_date,
        freshness_days=freshness_days,
    )

    return {
        "provider": provider,
        "series_id": series_id,
        "record_count": record_count,
        "missing_count": missing_count,
        "latest_date": latest_date,
        "last_retrieved_at": last_retrieved_at,
        "freshness_days": freshness_days,
        "status": status,
    }


def check_all(store: Store) -> list[dict[str, Any]]:
    """
    Check every provider/series combination stored in SQLite.
    """

    rows = store.con.execute(
        """
        SELECT DISTINCT provider, series_id
        FROM observations
        ORDER BY provider, series_id
        """
    ).fetchall()

    return [
        check_series(
            store,
            provider,
            series_id,
        )
        for provider, series_id in rows
    ]


def overall_status(results: list[dict[str, Any]]) -> str:
    """
    Calculate the overall health status.

    CRITICAL takes precedence over WARNING,
    which takes precedence over HEALTHY.
    """

    if not results:
        return "CRITICAL"

    statuses = {
        result["status"]
        for result in results
    }

    if "CRITICAL" in statuses:
        return "CRITICAL"

    if "WARNING" in statuses:
        return "WARNING"

    return "HEALTHY"
