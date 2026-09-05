import pytest

from iea.sizing import DEFAULT_SIZING_POLICY, SizingPolicy, calculate_exposure_budget, calculate_position_size, calculate_take_profit, calculate_trade_levels


def test_exposure_budget_scales_capital_by_advisory_multiplier():
    assert calculate_exposure_budget(100_000, 1.0) == 100_000.0
    assert calculate_exposure_budget(100_000, 0.75) == 75_000.0
    assert calculate_exposure_budget(100_000, 0.5) == 50_000.0
    assert calculate_exposure_budget(100_000, 0.0) == 0.0


def test_exposure_is_clamped_to_safe_default_bounds():
    assert calculate_exposure_budget(100_000, 1.5) == 100_000.0
    assert calculate_exposure_budget(100_000, -0.5) == 0.0


def test_negative_capital_produces_zero_budget():
    assert calculate_exposure_budget(-100_000, 1.0) == 0.0


def test_budget_rounding_is_deterministic():
    assert calculate_exposure_budget(123.456, 0.75) == 92.59


def test_custom_sizing_policy_can_tune_exposure_bounds():
    policy = SizingPolicy(minimum_exposure=0.1, maximum_exposure=0.6)
    assert policy.clamp_exposure(0.05) == 0.1
    assert policy.clamp_exposure(0.5) == 0.5
    assert policy.clamp_exposure(0.8) == 0.6


def test_default_sizing_policy_is_immutable():
    with pytest.raises((AttributeError, TypeError)):
        DEFAULT_SIZING_POLICY.maximum_exposure = 0.5


def test_position_size_is_limited_by_stop_loss_risk():
    assert calculate_position_size(100_000_000, 1.0, 100_000, 95_000) == 30_000_000.0


def test_position_size_is_capped_by_exposure_budget():
    assert calculate_position_size(100_000_000, 0.25, 100_000, 95_000) == 25_000_000.0


def test_position_size_zero_when_critical_exposure():
    assert calculate_position_size(100_000_000, 0.0, 100_000, 95_000) == 0.0


def test_position_size_rejects_invalid_prices():
    with pytest.raises(ValueError):
        calculate_position_size(100_000, 1.0, 0, 95)
    with pytest.raises(ValueError):
        calculate_position_size(100_000, 1.0, 100, 100)


def test_take_profit_for_buy_uses_two_to_one_risk_reward():
    assert calculate_take_profit(100, 95, "BUY", 2.0) == 110.0


def test_take_profit_for_sell_uses_two_to_one_risk_reward():
    assert calculate_take_profit(100, 105, "SELL", 2.0) == 90.0


def test_trade_levels_report_risk_reward():
    levels = calculate_trade_levels(100, 95, "BUY", 3.0)
    assert levels == {
        "entry_price": 100.0,
        "stop_loss": 95.0,
        "take_profit": 115.0,
        "risk_distance": 5.0,
        "reward_distance": 15.0,
        "risk_reward_ratio": 3.0,
    }


def test_trade_levels_reject_invalid_side_or_ratio():
    with pytest.raises(ValueError):
        calculate_take_profit(100, 95, "HOLD", 2.0)
    with pytest.raises(ValueError):
        calculate_take_profit(100, 95, "BUY", 0)
