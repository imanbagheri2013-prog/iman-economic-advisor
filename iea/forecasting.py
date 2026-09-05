from __future__ import annotations

from dataclasses import dataclass
from math import sqrt
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class ForecastResult:
    """Advisory time-series forecast with uncertainty and model diagnostics."""

    target: str
    horizon: int
    point_forecast: tuple[float, ...]
    lower: tuple[float, ...]
    upper: tuple[float, ...]
    model: str
    backtest_mae: float
    source_count: int = 1


def _validate_history(values: Iterable[float], minimum: int = 8) -> list[float]:
    history = [float(value) for value in values]
    if len(history) < minimum:
        raise ValueError(f"at least {minimum} observations are required")
    if any(value != value for value in history):
        raise ValueError("history must not contain NaN values")
    return history


def _exponential_smoothing(values: list[float], alpha: float = 0.3) -> float:
    if not 0 < alpha <= 1:
        raise ValueError("alpha must be in (0, 1]")
    level = values[0]
    for value in values[1:]:
        level = alpha * value + (1.0 - alpha) * level
    return level


def _ar1(values: list[float]) -> tuple[float, float]:
    """Fit y_t = intercept + phi*y_(t-1) using ordinary least squares."""
    x = values[:-1]
    y = values[1:]
    x_bar = mean(x)
    y_bar = mean(y)
    denominator = sum((item - x_bar) ** 2 for item in x)
    if denominator == 0:
        return y_bar, 0.0
    phi = sum((a - x_bar) * (b - y_bar) for a, b in zip(x, y)) / denominator
    phi = max(-0.99, min(0.99, phi))
    intercept = y_bar - phi * x_bar
    return intercept, phi


def _ar1_forecast(values: list[float], horizon: int) -> list[float]:
    intercept, phi = _ar1(values)
    current = values[-1]
    forecast: list[float] = []
    for _ in range(horizon):
        current = intercept + phi * current
        forecast.append(current)
    return forecast


def _one_step_mae(values: list[float], model: str) -> float:
    errors: list[float] = []
    start = max(5, len(values) // 2)
    for index in range(start, len(values)):
        train = values[:index]
        actual = values[index]
        if model == "exponential_smoothing":
            predicted = _exponential_smoothing(train)
        else:
            predicted = _ar1_forecast(train, 1)[0]
        errors.append(abs(actual - predicted))
    return mean(errors) if errors else 0.0


def forecast_series(
    values: Iterable[float],
    horizon: int,
    target: str,
    source_count: int = 1,
) -> ForecastResult:
    """Forecast a macro/market series using backtest-weighted ETS + AR(1).

    The engine is deliberately source-agnostic: source acquisition and economic
    feature construction are handled by the data layer. Forecasts are advisory
    and include a simple uncertainty band derived from rolling backtest error.
    """
    history = _validate_history(values)
    if horizon < 1:
        raise ValueError("horizon must be positive")
    if source_count < 1:
        raise ValueError("source_count must be positive")

    ets_mae = _one_step_mae(history, "exponential_smoothing")
    ar_mae = _one_step_mae(history, "ar1")
    eps = 1e-12
    ets_weight = 1.0 / max(ets_mae, eps)
    ar_weight = 1.0 / max(ar_mae, eps)
    total_weight = ets_weight + ar_weight
    ets_weight /= total_weight
    ar_weight /= total_weight

    level = _exponential_smoothing(history)
    ets_forecast = [level] * horizon
    ar_forecast = _ar1_forecast(history, horizon)
    point = [
        ets_weight * ets_value + ar_weight * ar_value
        for ets_value, ar_value in zip(ets_forecast, ar_forecast)
    ]

    error_scale = max(ets_mae * ets_weight + ar_mae * ar_weight, eps)
    z = 1.96
    lower = [value - z * error_scale for value in point]
    upper = [value + z * error_scale for value in point]

    return ForecastResult(
        target=target,
        horizon=horizon,
        point_forecast=tuple(point),
        lower=tuple(lower),
        upper=tuple(upper),
        model="backtest_weighted_ETS_AR1",
        backtest_mae=error_scale,
        source_count=source_count,
    )


def forecast_usd_market_rate(values: Iterable[float], horizon: int = 7, source_count: int = 1) -> ForecastResult:
    return forecast_series(values, horizon, target="USD_IRR_MARKET", source_count=source_count)


def forecast_gold_price(values: Iterable[float], horizon: int = 7, source_count: int = 1) -> ForecastResult:
    return forecast_series(values, horizon, target="GOLD_USD_OZ", source_count=source_count)


def forecast_inflation(values: Iterable[float], horizon: int = 12, source_count: int = 1) -> ForecastResult:
    return forecast_series(values, horizon, target="INFLATION", source_count=source_count)
