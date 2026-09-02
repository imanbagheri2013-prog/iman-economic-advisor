"""Unified health report for the economic data engine."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from .data_freshness import check_table_freshness
from .health_monitor import build_health_report


DEFAULT_DB = Path(os.getenv("IEA_DB_PATH", "data/iea.sqlite3"))


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_full_health_report(
    db_path: str | Path = DEFAULT_DB,
    registry_path: str | Path = "config/series.yaml",
) -> dict:
    monitor = build_health_report(db_path, registry_path)

    freshness = check_table_freshness(
        db_path=db_path,
        table_name="observations",
        timestamp_column="retrieved_at",
        max_age_hours=48,
    )

    monitor_status = monitor.get("status", "CRITICAL").lower()
    freshness_status = freshness.get("status", "critical").lower()

    if "critical" in {monitor_status, freshness_status}:
        overall_status = "critical"
    elif "warning" in {monitor_status, freshness_status} or "stale" in {monitor_status, freshness_status}:
        overall_status = "warning"
    else:
        overall_status = "ok"

    return {
        "service": "iman-economic-advisor",
        "component": "data-health",
        "checked_at": _utc_now(),
        "status": overall_status,
        "checks": {
            "database": monitor["database"],
            "data": monitor["data"],
            "freshness": freshness,
        },
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

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
