from datetime import date, datetime, timezone
from typing import Any

from .storage import Store


# Observation-age thresholds reflect the expected publication cadence of the
# registered macro series. These are intentionally conservative: they are
# health-monitor thresholds, not assumptions that missing observations should
# be fabricated or backfilled.
FRESHNESS_LIMITS_DAYS: dict[tuple[str, str], int] = {
    # BLS CPI series are monthly. A two-month gap is actionable; a longer gap
    # is critical because the pipeline should have received a new release.
    ("bls", "CUUR0000SA0"): 60,
    ("bls", "CUSR0000SA0L1E"): 60,
    # FRED daily market/financial series normally publish on business days.
    # A weekend/holiday gap is expected, but a week without a new observation
    # should be visible to the health monitor.
    ("fred", "DFF"): 7,
    ("fred", "DGS2"): 7,
    ("fred", "DGS10"): 7,
    ("fred", "DFII10"): 7,
    ("fred", "T10Y2Y"): 7,
    ("fred", "DTWEXBGS"): 7,
    ("fred", "VIXCLS"): 7,
    ("fred", "DCOILWTICO"): 7,
    ("fred", "DCOILBRENTEU"): 7,
    ("fred", "BAMLH0A0HYM2"): 7,
    # WALCL is weekly; allow a little more room for reporting lag.
    ("fred", "WALCL"): 14,
    # M2 is monthly; a missed release should be a warning, not a false daily
    # alarm. A two-month gap is actionable.
    ("fred", "M2SL"): 60,
}


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


def _freshness_limits(provider: str, series_id: str) -> tuple[int, int]:
    """Return warning and critical age limits for a provider/series."""
    warning_days = FRESHNESS_LIMITS_DAYS.get(
        (provider.strip().lower(), series_id.strip()),
        90,
    )
    # Critical means roughly two missed publication windows, while retaining
    # the historical 365-day safety floor for unknown/slow-moving series.
    critical_days = max(365, warning_days * 2)
    return warning_days, critical_days


def _status(
    record_count: int,
    missing_count: int,
    latest_date: str | None,
    freshness_days: int | None,
    warning_days: int = 90,
    critical_days: int = 365,
) -> str:
    """Calculate a health status using cadence-aware freshness thresholds."""

    if record_count == 0:
        return "CRITICAL"

    if missing_count > 0:
        return "WARNING"

    if latest_date is None:
        return "WARNING"

    if freshness_days is not None and freshness_days > critical_days:
        return "CRITICAL"

    if freshness_days is not None and freshness_days > warning_days:
        return "WARNING"

    return "HEALTHY"


def check_series(
    store: Store,
    provider: str,
    series_id: str,
) -> dict[str, Any]:
    """Check the health of a single provider/series combination."""

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
    warning_days, critical_days = _freshness_limits(provider, series_id)

    status = _status(
        record_count=record_count,
        missing_count=missing_count,
        latest_date=latest_date,
        freshness_days=freshness_days,
        warning_days=warning_days,
        critical_days=critical_days,
    )

    return {
        "provider": provider,
        "series_id": series_id,
        "record_count": record_count,
        "missing_count": missing_count,
        "latest_date": latest_date,
        "last_retrieved_at": last_retrieved_at,
        "freshness_days": freshness_days,
        "freshness_warning_days": warning_days,
        "freshness_critical_days": critical_days,
        "status": status,
    }


def check_all(store: Store) -> list[dict[str, Any]]:
    """Check every provider/series combination stored in SQLite."""

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
    """Calculate the overall health status."""

    if not results:
        return "CRITICAL"

    statuses = {result["status"] for result in results}

    if "CRITICAL" in statuses:
        return "CRITICAL"

    if "WARNING" in statuses:
        return "WARNING"

    return "HEALTHY"
