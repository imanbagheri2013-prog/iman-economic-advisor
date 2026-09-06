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
    """Return a stable capital snapshot suitable for reports and assistant output.

    The snapshot deliberately stores the current amount as input data while all
    risk/exposure rules remain percentage-based. Changing capital therefore
    rescales budgets and position sizes without changing the decision model.
    """
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
