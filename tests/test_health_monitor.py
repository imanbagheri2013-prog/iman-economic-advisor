from datetime import datetime, timezone
from pathlib import Path

from iea.health_monitor import (
    build_health_report,
    check_data,
    check_database,
    save_health_report,
)
from iea.models import Observation
from iea.storage import Store


def test_missing_database(tmp_path: Path):
    db_path = tmp_path / "missing.db"
    result = check_database(db_path)
    assert result["status"] == "CRITICAL"
    assert result["database_exists"] is False


def test_health_report_for_missing_database(tmp_path: Path):
    db_path = tmp_path / "missing.db"
    report = build_health_report(db_path)
    assert report["component"] == "data-health-monitor"
    assert report["status"] == "CRITICAL"


def test_save_health_report(tmp_path: Path):
    output = tmp_path / "health_report.json"
    report = {"status": "HEALTHY", "component": "data-health-monitor"}
    saved_path = save_health_report(report, output)
    assert saved_path.exists()
    assert saved_path == output
    assert '"status": "HEALTHY"' in output.read_text(encoding="utf-8")


def test_check_data_detects_missing_registered_series(tmp_path: Path):
    db_path = tmp_path / "data.db"
    registry = tmp_path / "series.yaml"
    registry.write_text("fred:\n  DFF: Fed Funds\n  DGS10: US 10Y\n", encoding="utf-8")

    store = Store(db_path)
    store.close()

    result = check_data(db_path, registry)
    assert result["status"] == "CRITICAL"
    assert result["expected_series"] == 2
    assert len(result["missing_series"]) == 2


def test_check_data_reports_series_health(tmp_path: Path):
    db_path = tmp_path / "data.db"
    registry = tmp_path / "series.yaml"
    registry.write_text("fred:\n  DFF: Fed Funds\n", encoding="utf-8")

    store = Store(db_path)
    try:
        obs = Observation(
            provider="fred",
            series_id="DFF",
            date=datetime(2026, 8, 28, tzinfo=timezone.utc),
            value=3.5,
            retrieved_at=datetime(2026, 8, 28, 10, tzinfo=timezone.utc),
            quality=100.0,
        )
        store.upsert(obs)
    finally:
        store.close()

    result = check_data(db_path, registry)
    assert result["checked_series"] == 1
    assert result["missing_series"] == []
    assert result["series"][0]["provider"] == "fred"
