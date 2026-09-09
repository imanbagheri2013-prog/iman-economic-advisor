from iea.advisor import build_equity_advisor_report
from iea.equity_fundamentals import FundamentalSnapshot


def _snapshot() -> FundamentalSnapshot:
    return FundamentalSnapshot(
        symbol="TEST",
        revenue=1_000_000,
        gross_profit=400_000,
        operating_profit=200_000,
        net_profit=150_000,
        operating_cash_flow=180_000,
        capex=50_000,
        total_debt=100_000,
        cash=100_000,
        equity=700_000,
        shares_outstanding=10_000,
        prior_revenue=800_000,
        prior_net_profit=100_000,
    )


def _market_report() -> dict:
    return {
        "score": 80.0,
        "coverage": 1.0,
        "regime": "RISK_ON",
        "factors": [
            {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
            {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
            {"name": "trend", "details": {"return_4h_pct": 2.0}},
        ],
        "data_quality": {"stale_factors": []},
        "portfolio": {"capital": 100_000_000.0},
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "live_market_intelligence": {
            "status": "OK",
            "market_status": "OPEN",
            "health_gate": "OPEN",
            "signals": [{"symbol": "TEST", "action": "BUY", "data_fresh": True}],
            "actionable_shortlist_symbols": ["TEST"],
        },
    }


def test_final_advisor_chain_reaches_capital_allocation():
    report = build_equity_advisor_report(
        snapshot=_snapshot(),
        current_price=100.0,
        method_values=[120.0],
        method_weights=[1.0],
        market_report=_market_report(),
        confidence=0.9,
        downside=0.10,
        upside=0.20,
    )

    decision = report["decision"]
    allocation = report["capital_allocation"]

    assert decision["final_action"] == "BUY"
    assert decision["capital_allocation_status"] == "READY"
    assert decision["live_market_validated"] is True
    assert allocation["status"] == "READY"
    assert allocation["action"] == "BUY"
    assert allocation["position_size"] > 0
    assert allocation["trade_levels"]["entry_price"] == 100.0
    assert allocation["trade_levels"]["stop_loss"] == 95.0
    assert allocation["execution"] == "NONE"


def test_final_advisor_chain_blocks_allocation_when_live_market_disagrees():
    market = _market_report()
    market["live_market_intelligence"]["signals"][0]["action"] = "SELL"

    report = build_equity_advisor_report(
        snapshot=_snapshot(),
        current_price=100.0,
        method_values=[120.0],
        method_weights=[1.0],
        market_report=market,
    )

    assert report["decision"]["final_action"] == "NO_TRADE"
    assert report["capital_allocation"]["status"] == "BLOCKED"
    assert report["capital_allocation"]["position_size"] == 0.0
    assert report["capital_allocation"]["execution"] == "NONE"
