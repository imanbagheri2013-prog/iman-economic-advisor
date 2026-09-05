from __future__ import annotations

import json

from iea import scheduler


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
