import json

from fastapi.testclient import TestClient

from iea.api import create_app


def _report():
    return {
        "status": "ok",
        "finished_at": "2026-09-06T12:00:00+00:00",
        "health_status": "HEALTHY",
        "intelligence": {
            "market_status": "OPEN",
            "regime": "RISK_ON",
            "score": 72.5,
            "data_quality": {"status": "GOOD"},
        },
        "central_bank": {
            "ingestion_status": "CONNECTED",
            "indicator_count": 17,
            "monetary_impulse": {"direction": "EXPANSION"},
            "monetary_policy_index": {"score": 20, "direction": "EXPANSIONARY"},
            "stored_observation_count": 40,
        },
        "portfolio": {
            "capital": 100_000_000,
            "equity": 101_000_000,
            "current_exposure": 30_000_000,
            "current_risk": 600_000,
            "drawdown": 0,
        },
    }


def test_health_endpoint():
    client = TestClient(create_app())
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "iea-assistant"}


def test_status_endpoint_reads_latest_report(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_report()), encoding="utf-8")
    client = TestClient(create_app(str(path)))

    response = client.get("/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["finished_at"] == "2026-09-06T12:00:00+00:00"
    assert payload["market_status"] == "OPEN"
    assert payload["central_bank"]["indicator_count"] == 17
    assert payload["portfolio"]["capital"] == 100_000_000


def test_answer_endpoint_uses_latest_report(tmp_path):
    path = tmp_path / "report.json"
    path.write_text(json.dumps(_report()), encoding="utf-8")
    client = TestClient(create_app(str(path)))

    response = client.get("/answer", params={"question": "وضعیت بازار چیست؟"})

    assert response.status_code == 200
    assert response.json()["assistant"] == "IEA"
