"""Data health checks for the economic data engine."""

from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path


DEFAULT_DB = Path("data/iea.sqlite3")


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def check_database(db_path: str | Path = DEFAULT_DB) -> dict:
    path = Path(db_path)

    if not path.exists():
        return {
            "status": "critical",
            "database_exists": False,
            "database": str(path),
            "error": "Database file does not exist.",
        }

    try:
        with sqlite3.connect(path) as conn:
            tables = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master "
                    "WHERE type='table'"
                ).fetchall()
            }

            table_stats = {}

            for table in sorted(tables):
                safe_table = table.replace('"', '""')
                count = conn.execute(
                    f'SELECT COUNT(*) FROM "{safe_table}"'
                ).fetchone()[0]

                table_stats[table] = {
                    "rows": count,
                }

        return {
            "status": "ok",
            "database_exists": True,
            "database": str(path),
            "checked_at": _utc_now().isoformat(),
            "tables": table_stats,
        }

    except Exception as exc:
        return {
            "status": "critical",
            "database_exists": True,
            "database": str(path),
            "error": str(exc),
        }


def build_health_report(db_path: str | Path = DEFAULT_DB) -> dict:
    database_health = check_database(db_path)

    status = database_health.get("status", "critical")

    report = {
        "service": "iman-economic-advisor",
        "component": "data-health-monitor",
        "checked_at": _utc_now().isoformat(),
        "status": status,
        "database": database_health,
    }

    return report


def save_health_report(
    report: dict,
    output_path: str | Path = "health_report.json",
) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    path.write_text(
        json.dumps(report, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    return path


def main() -> int:
    report = build_health_report()
    save_health_report(report)

    print(json.dumps(report, indent=2, ensure_ascii=False))

    return 0 if report["status"] == "ok" else 1


if __name__ == "__main__":
    raise SystemExit(main())
