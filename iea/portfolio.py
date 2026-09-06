from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class CapitalProfile:
    """Runtime capital profile; portfolio rules are ratios, not fixed amounts."""

    capital: float
    currency: str = "IRR"

    def __post_init__(self) -> None:
        amount = float(self.capital)
        if amount < 0:
            raise ValueError("capital must be non-negative")
        if not str(self.currency).strip():
            raise ValueError("currency must not be empty")


def normalize_capital(capital: float | None) -> float | None:
    """Normalize the currently available capital without embedding a fixed amount."""
    if capital is None:
        return None
    amount = float(capital)
    if amount < 0:
        raise ValueError("capital must be non-negative")
    return amount


def build_capital_snapshot(
    capital: float | None,
    *,
    currency: str = "IRR",
    source: str = "runtime",
) -> dict[str, object] | None:
    """Return a stable capital snapshot suitable for reports and assistant output."""
    amount = normalize_capital(capital)
    if amount is None:
        return None
    return {
        "capital": amount,
        "currency": str(currency).upper(),
        "source": str(source),
        "scaling_mode": "DYNAMIC_PERCENTAGE_BASED",
    }


def scale_ratio(amount: float, ratio: float) -> float:
    """Scale an amount by a bounded ratio, independent of account size."""
    value = max(0.0, float(amount))
    bounded_ratio = min(1.0, max(0.0, float(ratio)))
    return value * bounded_ratio


def build_portfolio_risk_budget(
    capital: float,
    *,
    exposure_multiplier: float,
    max_risk_per_trade: float = 0.015,
    max_total_risk: float = 0.06,
    max_positions: int = 6,
    invested_ratio: float = 0.0,
) -> dict[str, float | int | str]:
    """Build a scalable portfolio risk budget from the current capital.

    Every monetary limit is derived from capital ratios. The 100m IRR amount
    is therefore only an example/current input and never an architectural
    constant. Existing invested exposure can be supplied as a ratio of capital.
    """
    amount = normalize_capital(capital)
    assert amount is not None
    if max_risk_per_trade < 0 or max_total_risk < 0:
        raise ValueError("risk ratios must be non-negative")
    if max_positions < 1:
        raise ValueError("max_positions must be positive")

    exposure = min(1.0, max(0.0, float(exposure_multiplier)))
    invested = min(1.0, max(0.0, float(invested_ratio)))
    total_exposure_budget = scale_ratio(amount, exposure)
    available_exposure_budget = max(0.0, total_exposure_budget - scale_ratio(amount, invested))
    per_trade_risk_budget = scale_ratio(amount, max_risk_per_trade)
    total_risk_budget = scale_ratio(amount, max_total_risk)
    remaining_risk_budget = max(0.0, total_risk_budget - per_trade_risk_budget * 0)
    return {
        "capital": amount,
        "exposure_multiplier": exposure,
        "total_exposure_budget": round(total_exposure_budget, 2),
        "invested_ratio": invested,
        "available_exposure_budget": round(available_exposure_budget, 2),
        "max_risk_per_trade": float(max_risk_per_trade),
        "per_trade_risk_budget": round(per_trade_risk_budget, 2),
        "max_total_risk": float(max_total_risk),
        "total_risk_budget": round(total_risk_budget, 2),
        "remaining_risk_budget": round(remaining_risk_budget, 2),
        "max_positions": int(max_positions),
        "scaling_mode": "DYNAMIC_PERCENTAGE_BASED",
    }
