import pytest

from iea.sizing import DEFAULT_SIZING_POLICY, SizingPolicy, calculate_exposure_budget


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
