import pytest

from iea.equity_analysis import analyze_equity, equity_analysis_summary
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


def test_equity_analysis_combines_fundamentals_and_valuation():
    analysis = analyze_equity(
        snapshot(),
        current_price=20,
        method_values=[30, 28],
        method_weights=[0.6, 0.4],
        confidence=0.8,
        methods_used=["pe", "dcf_fcff"],
    )

    assert analysis.symbol == "TEST"
    assert analysis.fundamental.signal == "STRONG"
    assert analysis.valuation.base_value == pytest.approx(29.2)
    assert analysis.valuation.bear_value == pytest.approx(23.36)
    assert analysis.valuation.bull_value == pytest.approx(36.5)
    assert analysis.final_score > 70
    assert analysis.final_signal == "ATTRACTIVE"
    assert "material upside to intrinsic value" in analysis.reasons


def test_equity_analysis_summary_is_report_ready():
    analysis = analyze_equity(
        snapshot(),
        current_price=30,
        method_values=[30],
        method_weights=[1],
    )
    report = equity_analysis_summary(analysis)

    assert report["symbol"] == "TEST"
    assert report["fundamental"]["score"] == analysis.fundamental.score
    assert report["valuation"]["intrinsic_value"] == pytest.approx(30)
    assert report["final_signal"] == "NEUTRAL"
