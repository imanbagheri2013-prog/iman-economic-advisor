from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


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


def _position_exposure(position: dict[str, Any]) -> float:
    """Return current notional exposure for one position."""
    if "market_value" in position:
        return max(0.0, float(position["market_value"]))
    if "notional" in position:
        return max(0.0, float(position["notional"]))
    if "quantity" in position and "current_price" in position:
        return max(0.0, abs(float(position["quantity"])) * float(position["current_price"]))
    return 0.0


def _position_risk(position: dict[str, Any]) -> float:
    """Return estimated loss at stop for one position when enough data exists."""
    if "risk_amount" in position:
        return max(0.0, float(position["risk_amount"]))
    if "quantity" in position and "entry_price" in position and "stop_loss" in position:
        return max(0.0, abs(float(position["entry_price"]) - float(position["stop_loss"])) * abs(float(position["quantity"])))
    return 0.0


def summarize_positions(capital: float, positions: Iterable[dict[str, Any]] | None) -> dict[str, float | int | str]:
    """Summarize current exposure/risk from runtime positions without fixed capital assumptions."""
    amount = normalize_capital(capital)
    assert amount is not None
    items = [p for p in (positions or []) if isinstance(p, dict)]
    exposure = sum(_position_exposure(p) for p in items)
    risk = sum(_position_risk(p) for p in items)
    exposure_ratio = exposure / amount if amount > 0 else 0.0
    risk_ratio = risk / amount if amount > 0 else 0.0
    return {
        "position_count": len(items),
        "current_exposure": round(exposure, 2),
        "current_exposure_ratio": round(exposure_ratio, 6),
        "current_risk": round(risk, 2),
        "current_risk_ratio": round(risk_ratio, 6),
        "risk_tracking": "STOP_BASED_WHEN_AVAILABLE",
    }


def build_portfolio_risk_budget(
    capital: float,
    *,
    exposure_multiplier: float,
    max_risk_per_trade: float = 0.015,
    max_total_risk: float = 0.06,
    max_positions: int = 6,
    invested_ratio: float = 0.0,
    current_risk: float = 0.0,
    position_count: int = 0,
) -> dict[str, float | int | str]:
    """Build a scalable portfolio risk budget from current capital and state.

    All monetary limits are derived from runtime capital ratios. Existing exposure
    is represented by invested_ratio; current_risk and position_count can be supplied
    from live portfolio state to prevent stacking risk beyond the portfolio budget.
    """
    amount = normalize_capital(capital)
    assert amount is not None
    if max_risk_per_trade < 0 or max_total_risk < 0:
        raise ValueError("risk ratios must be non-negative")
    if max_positions < 1:
        raise ValueError("max_positions must be positive")
    if current_risk < 0:
        raise ValueError("current_risk must be non-negative")
    if position_count < 0:
        raise ValueError("position_count must be non-negative")

    exposure = min(1.0, max(0.0, float(exposure_multiplier)))
    invested = min(1.0, max(0.0, float(invested_ratio)))
    total_exposure_budget = scale_ratio(amount, exposure)
    available_exposure_budget = max(0.0, total_exposure_budget - scale_ratio(amount, invested))
    per_trade_risk_budget = scale_ratio(amount, max_risk_per_trade)
    total_risk_budget = scale_ratio(amount, max_total_risk)
    current_risk_value = max(0.0, float(current_risk))
    remaining_risk_budget = max(0.0, total_risk_budget - current_risk_value)
    positions_remaining = max(0, int(max_positions) - int(position_count))
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
        "current_risk": round(current_risk_value, 2),
        "remaining_risk_budget": round(remaining_risk_budget, 2),
        "max_positions": int(max_positions),
        "position_count": int(position_count),
        "positions_remaining": positions_remaining,
        "scaling_mode": "DYNAMIC_PERCENTAGE_BASED",
    }
