from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SizingPolicy:
    """Centralized policy for converting advisory exposure into capital budget."""

    minimum_exposure: float = 0.0
    maximum_exposure: float = 1.0
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
    """Return the advisory capital budget implied by an exposure multiplier.

    This function only calculates a budget. It never places, modifies, or
    executes a trade.
    """
    capital_amount = max(0.0, float(capital))
    exposure = policy.clamp_exposure(exposure_multiplier)
    return round(capital_amount * exposure, policy.rounding_digits)
