from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizingPolicy:
    """Centralized policy for advisory exposure and position sizing."""

    minimum_exposure: float = 0.0
    maximum_exposure: float = 1.0
    max_risk_per_trade: float = 0.015
    rounding_digits: int = 2

    def clamp_exposure(self, exposure_multiplier: float) -> float:
        exposure = float(exposure_multiplier)
        return min(self.maximum_exposure, max(self.minimum_exposure, exposure))


DEFAULT_SIZING_POLICY = SizingPolicy()


def calculate_exposure_budget(
    capital: float,
    exposure_multiplier: float,
    policy: SizingPolicy = DEFAULT_SIZING_POLICY,
) -> float:
    """Return the advisory capital budget implied by an exposure multiplier."""
    capital_amount = max(0.0, float(capital))
    exposure = policy.clamp_exposure(exposure_multiplier)
    return round(capital_amount * exposure, policy.rounding_digits)


def calculate_position_size(
    capital: float,
    exposure_multiplier: float,
    entry_price: float,
    stop_loss: float,
    policy: SizingPolicy = DEFAULT_SIZING_POLICY,
) -> float:
    """Return position notional constrained by exposure and stop-loss risk.

    The default maximum loss budget is 1.5% of capital. The result is
    advisory-only and never places, modifies, or executes a trade.
    """
    entry = float(entry_price)
    stop = float(stop_loss)
    if entry <= 0 or stop <= 0:
        raise ValueError("entry_price and stop_loss must be positive")
    if entry == stop:
        raise ValueError("entry_price and stop_loss must differ")
    risk_fraction = abs(entry - stop) / entry
    capital_amount = max(0.0, float(capital))
    risk_budget = capital_amount * max(0.0, float(policy.max_risk_per_trade))
    risk_limited_notional = risk_budget / risk_fraction
    exposure_budget = calculate_exposure_budget(capital_amount, exposure_multiplier, policy)
    return round(min(exposure_budget, risk_limited_notional), policy.rounding_digits)


def calculate_take_profit(
    entry_price: float,
    stop_loss: float,
    side: str,
    risk_reward_ratio: float = 2.0,
    rounding_digits: int = DEFAULT_SIZING_POLICY.rounding_digits,
) -> float:
    """Return an advisory take-profit price from entry, stop and R:R."""
    entry = float(entry_price)
    stop = float(stop_loss)
    ratio = float(risk_reward_ratio)
    normalized_side = str(side).upper()
    if entry <= 0 or stop <= 0:
        raise ValueError("entry_price and stop_loss must be positive")
    if entry == stop:
        raise ValueError("entry_price and stop_loss must differ")
    if ratio <= 0:
        raise ValueError("risk_reward_ratio must be positive")
    if normalized_side not in {"BUY", "SELL"}:
        raise ValueError("side must be BUY or SELL")
    risk_distance = abs(entry - stop)
    if normalized_side == "BUY":
        target = entry + risk_distance * ratio
    else:
        target = entry - risk_distance * ratio
    return round(target, rounding_digits)


def calculate_trade_levels(
    entry_price: float,
    stop_loss: float,
    side: str,
    risk_reward_ratio: float = 2.0,
    rounding_digits: int = DEFAULT_SIZING_POLICY.rounding_digits,
) -> dict[str, float]:
    """Return advisory entry/SL/TP levels and their risk/reward ratio."""
    entry = round(float(entry_price), rounding_digits)
    stop = round(float(stop_loss), rounding_digits)
    take_profit = calculate_take_profit(entry, stop, side, risk_reward_ratio, rounding_digits)
    risk_distance = abs(entry - stop)
    reward_distance = abs(take_profit - entry)
    return {
        "entry_price": entry,
        "stop_loss": stop,
        "take_profit": take_profit,
        "risk_distance": round(risk_distance, rounding_digits),
        "reward_distance": round(reward_distance, rounding_digits),
        "risk_reward_ratio": round(reward_distance / risk_distance, rounding_digits),
    }
