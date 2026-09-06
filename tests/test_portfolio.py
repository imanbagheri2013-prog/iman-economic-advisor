import pytest

from iea.portfolio import build_capital_snapshot, build_portfolio_risk_budget, normalize_capital, scale_ratio, summarize_positions


def test_capital_snapshot_is_dynamic_and_does_not_embed_a_fixed_amount():
    first = build_capital_snapshot(100_000_000)
    second = build_capital_snapshot(250_000_000)
    assert first["capital"] == 100_000_000.0
    assert second["capital"] == 250_000_000.0
    assert first["scaling_mode"] == second["scaling_mode"] == "DYNAMIC_PERCENTAGE_BASED"


def test_missing_capital_remains_unset():
    assert build_capital_snapshot(None) is None
    assert normalize_capital(None) is None


def test_capital_rejects_negative_values():
    with pytest.raises(ValueError):
        normalize_capital(-1)


def test_ratio_scaling_is_independent_of_account_size():
    assert scale_ratio(100_000_000, 0.25) == 25_000_000
    assert scale_ratio(400_000_000, 0.25) == 100_000_000


def test_ratio_scaling_is_bounded():
    assert scale_ratio(100, 2) == 100
    assert scale_ratio(100, -1) == 0


def test_portfolio_risk_budget_scales_all_limits_with_capital():
    small = build_portfolio_risk_budget(100_000_000, exposure_multiplier=0.75)
    large = build_portfolio_risk_budget(400_000_000, exposure_multiplier=0.75)
    assert small["total_exposure_budget"] == 75_000_000
    assert large["total_exposure_budget"] == 300_000_000
    assert small["per_trade_risk_budget"] == 1_500_000
    assert large["per_trade_risk_budget"] == 6_000_000
    assert small["total_risk_budget"] == 6_000_000
    assert large["total_risk_budget"] == 24_000_000
    assert small["scaling_mode"] == large["scaling_mode"] == "DYNAMIC_PERCENTAGE_BASED"


def test_existing_invested_ratio_reduces_available_exposure_without_fixed_amounts():
    budget = build_portfolio_risk_budget(200_000_000, exposure_multiplier=0.8, invested_ratio=0.3)
    assert budget["total_exposure_budget"] == 160_000_000
    assert budget["available_exposure_budget"] == 100_000_000


def test_portfolio_risk_budget_rejects_invalid_position_limit():
    with pytest.raises(ValueError):
        build_portfolio_risk_budget(100, exposure_multiplier=0.5, max_positions=0)


def test_position_summary_tracks_exposure_and_stop_based_risk():
    positions = [
        {"quantity": 10, "entry_price": 100, "stop_loss": 90, "current_price": 105},
        {"market_value": 25_000, "risk_amount": 500},
    ]
    summary = summarize_positions(100_000, positions)
    assert summary["position_count"] == 2
    assert summary["current_exposure"] == 26_050
    assert summary["current_exposure_ratio"] == pytest.approx(0.2605)
    assert summary["current_risk"] == 600
    assert summary["current_risk_ratio"] == pytest.approx(0.006)


def test_remaining_risk_budget_uses_current_risk():
    budget = build_portfolio_risk_budget(100_000_000, exposure_multiplier=0.8, current_risk=5_000_000, position_count=2)
    assert budget["total_risk_budget"] == 6_000_000
    assert budget["remaining_risk_budget"] == 1_000_000
    assert budget["positions_remaining"] == 4


def test_max_positions_blocks_new_budget_when_limit_is_reached():
    budget = build_portfolio_risk_budget(100_000_000, exposure_multiplier=0.8, max_positions=2, position_count=2)
    assert budget["positions_remaining"] == 0
    assert budget["remaining_risk_budget"] == 6_000_000
