"""Unified health report for the economic data engine."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from .data_freshness import check_table_freshness
from .health_monitor import check_database


DEFAULT_DB = Path("data/economic_data.db")


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_full_health_report(
    db_path: str | Path = DEFAULT_DB,
) -> dict:
    database = check_database(db_path)

    freshness = check_table_freshness(
        db_path=db_path,
        table_name="observations",
        timestamp_column="updated_at",
        max_age_hours=48,
    )

    checks = {
        "database": database,
        "freshness": freshness,
    }

    statuses = {
        database.get("status"),
        freshness.get("status"),
    }

    if "critical" in statuses:
        overall_status = "critical"
    elif "stale" in statuses:
        overall_status = "stale"
    elif "warning" in statuses:
        overall_status = "warning"
    else:
        overall_status = "ok"

    return {
        "service": "iman-economic-advisor",
        "component": "data-health",
        "checked_at": _utc_now(),
        "status": overall_status,
        "checks": checks,
    }


def save_report(
    report: dict,
    output_path: str | Path = "health_report.json",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
            default=str,
        ),
        encoding="utf-8",
    )

    return path


def main() -> int:
    report = build_full_health_report()

    save_report(report)

    print(
        json.dumps(
            report,
            indent=2,
            ensure_ascii=False,
        )
    )

    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
