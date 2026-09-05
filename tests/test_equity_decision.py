import pytest

from iea.advisor import build_equity_advisor_report
from iea.equity_analysis import analyze_equity
from iea.equity_decision import build_equity_market_decision
from iea.equity_fundamentals import FundamentalSnapshot


def snapshot() -> FundamentalSnapshot:
    return FundamentalSnapshot(
        symbol="TEST",
        revenue=1000,
        gross_profit=400,
        operating_profit=200,
        net_profit=120,
        operating_cash_flow=180,
        capex=50,
        total_debt=200,
        cash=100,
        equity=800,
        shares_outstanding=100,
        prior_revenue=800,
        prior_net_profit=100,
    )


def equity_analysis():
    return analyze_equity(
        snapshot(),
        current_price=20,
        method_values=[30, 28],
        method_weights=[0.6, 0.4],
        confidence=0.8,
        methods_used=["pe", "dcf_fcff"],
    )


def test_equity_and_market_scores_are_combined_before_policy_gate():
    result = build_equity_market_decision(
        equity_analysis(),
        {
            "score": 70,
            "coverage": 1.0,
            "factors": [
                {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
                {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
            ],
        },
    )
    assert result["equity_score"] > 70
    assert result["market_score"] == 70
    assert result["combined_score"] == pytest.approx(81.36)
    assert result["regime"] == "RISK_ON"
    assert result["decision"]["action"] == "BUY_BIAS"


def test_market_risk_flags_still_block_combined_equity_decision():
    result = build_equity_market_decision(
        equity_analysis(),
        {
            "score": 80,
            "coverage": 1.0,
            "factors": [
                {"name": "news_risk", "details": {"risk_regime": "HIGH_RISK"}},
                {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
            ],
        },
    )
    assert result["decision"]["action"] == "NO_TRADE"
    assert result["decision"]["risk_tier"] == "CRITICAL"
    assert result["decision"]["exposure_multiplier"] == 0.0


def test_missing_market_score_fails_closed():
    result = build_equity_market_decision(
        equity_analysis(),
        {"score": None, "coverage": 0.0, "factors": []},
    )
    assert result["combined_score"] is None
    assert result["regime"] == "INSUFFICIENT_DATA"
    assert result["decision"]["action"] == "NO_TRADE"


def test_weights_are_normalized():
    result = build_equity_market_decision(
        equity_analysis(),
        {"score": 50, "coverage": 1.0, "factors": []},
        equity_weight=2.0,
        market_weight=3.0,
    )
    assert result["equity_weight"] == pytest.approx(0.4)
    assert result["market_weight"] == pytest.approx(0.6)


def test_end_to_end_equity_advisor_report_contains_all_layers():
    result = build_equity_advisor_report(
        snapshot=snapshot(),
        current_price=20,
        method_values=[30, 28],
        method_weights=[0.6, 0.4],
        market_report={
            "score": 70,
            "coverage": 1.0,
            "factors": [
                {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
                {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
            ],
        },
        confidence=0.8,
        methods_used=["pe", "dcf_fcff"],
    )
    assert result["engine"] == "iea_equity_advisor_v1"
    assert result["symbol"] == "TEST"
    assert result["analysis"]["final_score"] == pytest.approx(98.4)
    assert result["market"]["score"] == 70
    assert result["combined_score"] == pytest.approx(81.36)
    assert result["decision"]["action"] == "BUY_BIAS"
    assert result["analysis"]["valuation"]["intrinsic_value"] == pytest.approx(29.2)
