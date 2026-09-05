import pytest

from iea.equity_fundamentals import (
    FundamentalSnapshot,
    calculate_fundamental_metrics,
    score_fundamentals,
)


def snapshot(**overrides):
    data = {
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
    data.update(overrides)
    return FundamentalSnapshot(**data)


def test_calculate_fundamental_metrics():
    metrics = calculate_fundamental_metrics(snapshot())
    assert metrics.gross_margin == pytest.approx(0.40)
    assert metrics.operating_margin == pytest.approx(0.20)
    assert metrics.net_margin == pytest.approx(0.12)
    assert metrics.roe == pytest.approx(0.15)
    assert metrics.debt_to_equity == pytest.approx(0.25)
    assert metrics.free_cash_flow == pytest.approx(130)
    assert metrics.revenue_growth == pytest.approx(0.25)
    assert metrics.net_profit_growth == pytest.approx(0.20)


def test_strong_fundamentals_score_positive():
    quality = score_fundamentals(snapshot())
    assert quality.symbol == "TEST"
    assert quality.score >= 70
    assert quality.signal == "STRONG"
    assert "positive free cash flow" in quality.reasons


def test_weak_fundamentals_are_penalized():
    quality = score_fundamentals(
        snapshot(
            gross_profit=-100,
            operating_profit=-150,
            net_profit=-200,
            operating_cash_flow=-100,
            total_debt=3000,
            prior_revenue=1200,
            prior_net_profit=100,
        )
    )
    assert quality.score < 50
    assert quality.signal == "WEAK"


def test_revenue_is_required_to_be_positive():
    with pytest.raises(ValueError):
        calculate_fundamental_metrics(snapshot(revenue=0))
