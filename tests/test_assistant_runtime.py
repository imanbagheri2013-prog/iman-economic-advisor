import json

import pytest

from iea.assistant_runtime import answer, load_report


def _report():
    return {
        "status": "ok",
        "finished_at": "2026-09-06T12:00:00+00:00",
        "health_status": "HEALTHY",
        "intelligence": {
            "market_status": "OPEN",
            "regime": "RISK_ON",
            "score": 72.5,
            "coverage": 1.0,
            "decision": {"action": "BUY_BIAS", "reason": "test"},
            "data_quality": {"status": "GOOD"},
        },
        "central_bank": {
            "ingestion_status": "CONNECTED",
            "indicator_count": 2,
            "indicators": {"liquidity_m2": {"value": 100}},
            "monetary_growth": {"liquidity_growth": 0.25},
            "monetary_impulse": {"direction": "EXPANSION"},
            "monetary_policy_index": {"score": 20, "direction": "EXPANSIONARY"},
            "policy_transmission": {"currency_in_circulation_growth": 0.1},
            "revision_count": 0,
            "stored_observation_count": 4,
        },
    }


def test_load_report_rejects_non_object(tmp_path):
    path = tmp_path / "report.json"
    path.write_text("[]", encoding="utf-8")
    with pytest.raises(ValueError, match="JSON object"):
        load_report(path)


def test_answer_uses_latest_report(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_report()), encoding="utf-8")
    response = answer("وضعیت بانک مرکزی و نقدینگی چطور است؟", path)
    assert response["assistant"] == "IEA"
    assert response["intent"] == "monetary"
    assert response["answer"]["monetary_growth"]["liquidity_growth"] == 0.25


def test_answer_fails_clearly_for_missing_report(tmp_path):
    with pytest.raises(RuntimeError, match="Unable to load IEA report"):
        answer("وضعیت بازار چیست؟", tmp_path / "missing.json")
