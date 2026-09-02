"""Unified data health monitor for the economic data engine."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

import yaml

from .health import check_series, overall_status
from .storage import Store


DEFAULT_DB = Path(os.getenv("IEA_DB_PATH", "data/iea.sqlite3"))
DEFAULT_REGISTRY = Path("config/series.yaml")


def _load_registry(registry_path: str | Path = DEFAULT_REGISTRY) -> dict[str, dict[str, str]]:
    path = Path(registry_path)
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return {
        provider: dict(series or {})
        for provider, series in payload.items()
        if isinstance(series, dict)
    }


def _expected_series(registry: dict[str, dict[str, str]]) -> list[tuple[str, str]]:
    return sorted(
        (provider, series_id)
        for provider, series in registry.items()
        for series_id in series
    )


def check_database(db_path: str | Path = DEFAULT_DB) -> dict[str, Any]:
    path = Path(db_path)
    if not path.exists():
        return {
            "status": "CRITICAL",
            "database_exists": False,
            "database": str(path),
            "error": "Database file does not exist.",
        }

    try:
        store = Store(path)
        try:
            tables = {
                row[0]
                for row in store.con.execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                ).fetchall()
            }
            table_stats = {}
            for table in sorted(tables):
                safe_table = table.replace('"', '""')
                count = store.con.execute(
                    f'SELECT COUNT(*) FROM "{safe_table}"'
                ).fetchone()[0]
                table_stats[table] = {"rows": int(count)}
        finally:
            store.close()
        return {
            "status": "HEALTHY",
            "database_exists": True,
            "database": str(path),
            "tables": table_stats,
        }
    except Exception:
        return {
            "status": "CRITICAL",
            "database_exists": True,
            "database": str(path),
            "error": "Database health check failed.",
        }


def check_data(
    db_path: str | Path = DEFAULT_DB,
    registry_path: str | Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    if not Path(db_path).exists():
        return {"status": "CRITICAL", "expected_series": 0, "checked_series": 0, "missing_series": [], "series": []}

    store = Store(db_path)
    try:
        registry = _load_registry(registry_path)
        expected = _expected_series(registry)
        results = [check_series(store, provider, series_id) for provider, series_id in expected]
        stored = {
            (provider, series_id)
            for provider, series_id in store.con.execute(
                "SELECT DISTINCT provider, series_id FROM observations"
            ).fetchall()
        }
        missing_series = [
            {"provider": provider, "series_id": series_id}
            for provider, series_id in expected
            if (provider, series_id) not in stored
        ]
        status = "CRITICAL" if missing_series else overall_status(results)
        return {
            "status": status,
            "expected_series": len(expected),
            "checked_series": len(results),
            "missing_series": missing_series,
            "series": results,
        }
    finally:
        store.close()


def build_health_report(
    db_path: str | Path = DEFAULT_DB,
    registry_path: str | Path = DEFAULT_REGISTRY,
) -> dict[str, Any]:
    database = check_database(db_path)
    data = check_data(db_path, registry_path) if database["database_exists"] else {
        "status": "CRITICAL",
        "expected_series": 0,
        "checked_series": 0,
        "missing_series": [],
        "series": [],
    }
    statuses = [database["status"], data["status"]]
    status = "CRITICAL" if "CRITICAL" in statuses else "WARNING" if "WARNING" in statuses else "HEALTHY"
    return {
        "service": "iman-economic-advisor",
        "component": "data-health-monitor",
        "status": status,
        "database": database,
        "data": data,
    }


def save_health_report(report: dict[str, Any], output_path: str | Path = "health_report.json") -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    return path


def main() -> int:
    report = build_health_report()
    save_health_report(report)
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["status"] != "CRITICAL" else 1


if __name__ == "__main__":
    raise SystemExit(main())
