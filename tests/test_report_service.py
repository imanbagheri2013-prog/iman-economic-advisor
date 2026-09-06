import json

import pytest

from iea.report_service import load_latest_report


def _report(timestamp="2026-09-06T12:00:00+00:00"):
    return {
        "status": "ok",
        "finished_at": timestamp,
        "pipeline_status": "OK",
    }


def test_load_latest_report_adds_freshness_metadata(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_report()), encoding="utf-8")

    report = load_latest_report(path)

    assert report["pipeline_status"] == "OK"
    assert report["report_meta"]["fresh"] is True
    assert report["report_meta"]["max_age_seconds"] == 21600


def test_load_latest_report_rejects_error_report(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps({"status": "error", "finished_at": "2026-09-06T12:00:00+00:00"}), encoding="utf-8")

    with pytest.raises(ValueError, match="trusted successful report"):
        load_latest_report(path)


def test_load_latest_report_marks_old_report_stale(tmp_path, monkeypatch):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_report("2020-01-01T00:00:00+00:00")), encoding="utf-8")
    monkeypatch.setenv("IEA_REPORT_MAX_AGE_SECONDS", "60")

    report = load_latest_report(path)

    assert report["report_meta"]["fresh"] is False
    assert report["report_meta"]["age_seconds"] > 60
