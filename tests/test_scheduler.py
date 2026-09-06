from __future__ import annotations

import json

from iea import scheduler
from iea.central_bank import normalize_observation


SNAPSHOT = {
    "symbol": "TEST",
    "revenue": 1000,
    "gross_profit": 400,
    "operating_profit": 200,
    "net_profit": 120,
    "operating_cash_flow": 180,
    "capex": 50,
    "total_debt": 200,
    "cash": 100,
    "equity": 800,
    "shares_outstanding": 100,
    "prior_revenue": 800,
    "prior_net_profit": 100,
}


def test_equity_cycle_is_optional_when_input_path_is_missing(monkeypatch, tmp_path):
    monkeypatch.setenv("IEA_EQUITY_INPUT_PATH", str(tmp_path / "missing.json"))

    assert scheduler._build_equity_cycle({"score": 70, "coverage": 1.0}, None) is None


def test_equity_cycle_uses_scheduled_market_report(monkeypatch, tmp_path):
    payload_path = tmp_path / "equity.json"
    payload_path.write_text(
        json.dumps(
            {
                "snapshot": SNAPSHOT,
                "current_price": 20,
                "method_values": [30, 28],
                "method_weights": [0.6, 0.4],
                "methods_used": ["pe", "dcf_fcff"],
                "confidence": 0.8,
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("IEA_EQUITY_INPUT_PATH", str(payload_path))

    result = scheduler._build_equity_cycle(
        {
            "score": 70,
            "coverage": 1.0,
            "regime": "RISK_ON",
            "factors": [],
        },
        100_000_000,
    )

    assert result["symbol"] == "TEST"
    assert result["market"]["score"] == 70
    assert result["combined_score"] == 81.36


def test_equity_cycle_passes_full_market_intelligence(monkeypatch, tmp_path):
    payload_path = tmp_path / "equity.json"
    payload_path.write_text(
        json.dumps(
            {
                "snapshot": SNAPSHOT,
                "current_price": 20,
                "method_values": [30, 28],
                "method_weights": [0.6, 0.4],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("IEA_EQUITY_INPUT_PATH", str(payload_path))

    captured: dict = {}

    def fake_build_equity_advisor_report(**kwargs):
        captured.update(kwargs)
        return {"ok": True}

    monkeypatch.setattr(scheduler, "build_equity_advisor_report", fake_build_equity_advisor_report)

    intelligence = {
        "score": 61.5,
        "coverage": 0.875,
        "regime": "NEUTRAL",
        "factors": [
            {
                "name": "liquidity",
                "status": "OK",
                "score": 55,
                "confidence": 0.9,
                "details": {"depth_imbalance": 0.12},
            }
        ],
        "decision": {"action": "HOLD"},
    }

    assert scheduler._build_equity_cycle(intelligence, 100_000_000) == {"ok": True}
    assert captured["market_report"] is intelligence
    assert captured["market_report"]["factors"][0]["name"] == "liquidity"


def test_equity_cycle_rejects_invalid_payload(monkeypatch, tmp_path):
    payload_path = tmp_path / "invalid.json"
    payload_path.write_text(json.dumps({"snapshot": SNAPSHOT}), encoding="utf-8")
    monkeypatch.setenv("IEA_EQUITY_INPUT_PATH", str(payload_path))

    try:
        scheduler._build_equity_cycle({"score": 70, "coverage": 1.0}, None)
    except ValueError as exc:
        assert "missing equity payload fields" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("invalid equity payload must fail fast")


def test_save_report_persists_json(monkeypatch, tmp_path):
    report_path = tmp_path / "health_report.json"
    monkeypatch.setattr(scheduler, "REPORT_PATH", report_path)

    scheduler._save_report({"status": "ok", "observations": 42})

    saved = json.loads(report_path.read_text(encoding="utf-8"))
    assert saved == {"status": "ok", "observations": 42}


def test_central_bank_report_builds_growth_impulse_and_policy_index():
    class FakeStore:
        def central_bank_observations(self):
            return [
                normalize_observation("monetary_base", 100, "IRR_bn", "2026-08-01"),
                normalize_observation("monetary_base", 140, "IRR_bn", "2026-09-01"),
                normalize_observation("liquidity_m2", 200, "IRR_bn", "2026-08-01"),
                normalize_observation("liquidity_m2", 260, "IRR_bn", "2026-09-01"),
                normalize_observation("bank_credit", 100, "IRR_bn", "2026-08-01"),
                normalize_observation("bank_credit", 130, "IRR_bn", "2026-09-01"),
                normalize_observation("policy_rate", 20, "%", "2026-08-01"),
                normalize_observation("policy_rate", 18, "%", "2026-09-01"),
                normalize_observation("reserve_requirement", 10, "%", "2026-08-01"),
                normalize_observation("reserve_requirement", 9, "%", "2026-09-01"),
                normalize_observation("open_market_operations", 5, "IRR_bn", "2026-09-01"),
            ]

        def count_central_bank(self):
            return 11

    report = scheduler._central_bank_report(FakeStore(), {"cbi_data_url": "https://official.example/cbi.csv"})

    assert report["ingestion_status"] == "CONNECTED"
    assert report["monetary_growth"]["monetary_base_growth"] == 40.0
    assert report["monetary_impulse"]["direction"] == "STRONG_EXPANSION"
    assert report["monetary_policy_index"]["status"] == "OK"
    assert report["monetary_policy_index"]["direction"] == "EXPANSIONARY"
    assert report["policy_transmission"]["currency_in_circulation_growth"] is None
