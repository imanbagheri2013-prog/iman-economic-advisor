import json

from iea import runtime


def payload():
    return {
        "snapshot": {
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
        },
        "current_price": 20,
        "method_values": [30, 28],
        "method_weights": [0.6, 0.4],
        "methods_used": ["pe", "dcf_fcff"],
        "capital": 100_000_000,
    }


def test_load_equity_payload(tmp_path):
    path = tmp_path / "equity.json"
    path.write_text(json.dumps(payload()), encoding="utf-8")

    loaded = runtime.load_equity_payload(path)

    assert loaded["snapshot"]["symbol"] == "TEST"
    assert loaded["current_price"] == 20


def test_load_equity_payload_rejects_missing_fields(tmp_path):
    path = tmp_path / "equity.json"
    path.write_text(json.dumps({"snapshot": {}}), encoding="utf-8")

    try:
        runtime.load_equity_payload(path)
    except ValueError as exc:
        assert "current_price" in str(exc)
    else:
        raise AssertionError("expected ValueError")


def test_live_runtime_connects_market_pipeline_to_unified_advisor(monkeypatch):
    market_report = {
        "score": 70,
        "coverage": 1.0,
        "factors": [
            {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
            {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
        ],
    }
    called = {}

    def fake_market(store, **kwargs):
        called["store"] = store
        called["kwargs"] = kwargs
        return market_report

    monkeypatch.setattr(runtime, "analyze_eight_factor", fake_market)

    result = runtime.build_live_equity_advisor_report(
        object(),
        payload(),
        capital=100_000_000,
    )

    assert called["store"] is not None
    assert result["symbol"] == "TEST"
    assert result["market"]["score"] == 70
    assert result["combined_score"] == 81.36
    assert result["decision"]["action"] == "BUY_BIAS"
