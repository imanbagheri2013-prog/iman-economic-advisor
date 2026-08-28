from pathlib import Path

from iea.health_monitor import (
    build_health_report,
    check_database,
    save_health_report,
)


def test_missing_database(tmp_path: Path):
    db_path = tmp_path / "missing.db"

    result = check_database(db_path)

    assert result["status"] == "critical"
    assert result["database_exists"] is False


def test_health_report_for_missing_database(tmp_path: Path):
    db_path = tmp_path / "missing.db"

    report = build_health_report(db_path)

    assert report["component"] == "data-health-monitor"
    assert report["status"] == "critical"


def test_save_health_report(tmp_path: Path):
    output = tmp_path / "health_report.json"

    report = {
        "status": "ok",
        "component": "data-health-monitor",
    }

    saved_path = save_health_report(report, output)

    assert saved_path.exists()
    assert saved_path == output
    assert '"status": "ok"' in output.read_text(encoding="utf-8")
