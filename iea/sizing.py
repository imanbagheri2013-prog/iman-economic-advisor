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


def calculate_exposure_budget(
    capital: float,
    exposure_multiplier: float,
    policy: SizingPolicy = SizingPolicy(),
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
    policy: SizingPolicy = SizingPolicy(),
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
    if risk_fraction <= 0:
        return 0.0

    capital_amount = max(0.0, float(capital))
    risk_budget = capital_amount * max(0.0, float(policy.max_risk_per_trade))
    risk_limited_notional = risk_budget / risk_fraction
    exposure_budget = calculate_exposure_budget(capital_amount, exposure_multiplier, policy)
    return round(min(exposure_budget, risk_limited_notional), policy.rounding_digits)
