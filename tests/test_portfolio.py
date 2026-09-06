import pytest

from iea.portfolio import build_capital_snapshot, normalize_capital, scale_ratio


def test_capital_snapshot_is_dynamic_and_does_not_embed_a_fixed_amount():
    first = build_capital_snapshot(100_000_000)
    second = build_capital_snapshot(250_000_000)

    assert first["capital"] == 100_000_000.0
    assert second["capital"] == 250_000_000.0
    assert first["scaling_mode"] == "DYNAMIC_PERCENTAGE_BASED"
    assert second["scaling_mode"] == "DYNAMIC_PERCENTAGE_BASED"


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
