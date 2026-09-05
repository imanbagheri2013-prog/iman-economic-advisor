import pytest

from iea.forecasting import forecast_gold_price, forecast_inflation, forecast_series, forecast_usd_market_rate


def test_forecast_series_is_deterministic_and_returns_interval():
    values = [100, 101, 102, 104, 103, 105, 107, 108, 110, 111]
    result = forecast_series(values, horizon=3, target="TEST", source_count=2)
    assert result.target == "TEST"
    assert result.horizon == 3
    assert len(result.point_forecast) == 3
    assert len(result.lower) == 3
    assert len(result.upper) == 3
    assert result.model == "backtest_weighted_ETS_AR1"
    assert result.source_count == 2
    assert result.backtest_mae >= 0
    for point, lower, upper in zip(result.point_forecast, result.lower, result.upper):
        assert lower <= point <= upper


def test_forecast_wrappers_use_expected_targets():
    values = [100, 101, 102, 103, 104, 105, 106, 107]
    assert forecast_usd_market_rate(values, horizon=2).target == "USD_IRR_MARKET"
    assert forecast_gold_price(values, horizon=2).target == "GOLD_USD_OZ"
    assert forecast_inflation(values, horizon=2).target == "INFLATION"


@pytest.mark.parametrize(
    "values,horizon",
    [([1, 2, 3], 1), ([1, 2, 3, 4, 5, 6, 7, float('nan')], 1)],
)
def test_forecast_rejects_invalid_history(values, horizon):
    with pytest.raises(ValueError):
        forecast_series(values, horizon=horizon, target="TEST")


def test_forecast_rejects_invalid_horizon_and_source_count():
    values = [1, 2, 3, 4, 5, 6, 7, 8]
    with pytest.raises(ValueError):
        forecast_series(values, horizon=0, target="TEST")
    with pytest.raises(ValueError):
        forecast_series(values, horizon=1, target="TEST", source_count=0)
