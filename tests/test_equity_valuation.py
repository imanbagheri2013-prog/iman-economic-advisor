import pytest

from iea.equity_valuation import (
    build_equity_valuation,
    dcf_equity_value,
    ev_ebitda_equity_value,
    pe_value,
    valuation_summary,
    weighted_fair_value,
)


def test_dcf_returns_positive_equity_value_per_share():
    value = dcf_equity_value([100, 110, 120, 130, 140], 0.15, 0.04, net_debt=200, shares_outstanding=100)
    assert value > 0


def test_relative_valuation_methods():
    assert pe_value(10, 8) == 80
    assert ev_ebitda_equity_value(1000, 6, 2000, 100) == 40


def test_weighted_fair_value_normalizes_weights():
    assert weighted_fair_value([100, 200], [1, 3]) == 175


def test_build_equity_valuation_creates_bear_base_bull_scenarios():
    valuation = build_equity_valuation(
        "TEST",
        100,
        [120, 140],
        [1, 1],
        confidence=0.8,
        downside=0.2,
        upside=0.25,
        methods_used=("DCF", "P_E"),
    )
    assert valuation.symbol == "TEST"
    assert valuation.base_value == 130
    assert valuation.bear_value == 104
    assert valuation.bull_value == 162.5
    assert valuation.scenarios[1].upside_pct == pytest.approx(30.0)
    assert valuation.scenarios[1].confidence == 0.8
    assert valuation.methods_used == ("DCF", "P_E")


def test_valuation_summary_is_report_ready():
    valuation = build_equity_valuation("abc", 100, [120], [1], confidence=0.9)
    report = valuation_summary(valuation)
    assert report["symbol"] == "ABC"
    assert report["intrinsic_value"] == 120
    assert report["upside_to_intrinsic_pct"] == pytest.approx(20.0)
    assert [item["name"] for item in report["scenarios"]] == ["BEAR", "BASE", "BULL"]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"current_price": 0, "method_values": [100], "method_weights": [1]},
        {"current_price": 100, "method_values": [100], "method_weights": [0]},
        {"current_price": 100, "method_values": [100], "method_weights": [1], "confidence": 1.1},
    ],
)
def test_equity_valuation_rejects_invalid_inputs(kwargs):
    with pytest.raises(ValueError):
        build_equity_valuation("TEST", **kwargs)


def test_dcf_rejects_terminal_growth_at_or_above_discount_rate():
    with pytest.raises(ValueError):
        dcf_equity_value([100, 110], 0.08, 0.08)
