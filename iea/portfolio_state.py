from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable

from .portfolio import summarize_positions


@dataclass(frozen=True)
class PortfolioState:
    """Normalized runtime portfolio state; all ratios scale with current capital."""

    capital: float
    cash: float
    positions: tuple[dict[str, Any], ...]
    realized_pnl: float = 0.0
    unrealized_pnl: float = 0.0
    peak_equity: float | None = None

    def __post_init__(self) -> None:
        if self.capital < 0:
            raise ValueError("capital must be non-negative")
        if self.cash < 0:
            raise ValueError("cash must be non-negative")
        if self.peak_equity is not None and self.peak_equity < 0:
            raise ValueError("peak_equity must be non-negative")


def normalize_positions(positions: Iterable[dict[str, Any]] | None) -> tuple[dict[str, Any], ...]:
    """Keep only dictionary positions and normalize numeric fields used by risk state."""
    normalized: list[dict[str, Any]] = []
    for raw in positions or []:
        if not isinstance(raw, dict):
            continue
        position = dict(raw)
        for key in ("quantity", "entry_price", "stop_loss", "current_price", "market_value", "notional", "risk_amount", "realized_pnl", "unrealized_pnl"):
            if key in position and position[key] is not None:
                position[key] = float(position[key])
        normalized.append(position)
    return tuple(normalized)


def build_portfolio_state(
    capital: float,
    *,
    cash: float,
    positions: Iterable[dict[str, Any]] | None = None,
    realized_pnl: float = 0.0,
    unrealized_pnl: float = 0.0,
    peak_equity: float | None = None,
) -> dict[str, Any]:
    """Build a serializable portfolio snapshot for decisions, persistence and assistant output."""
    normalized = normalize_positions(positions)
    summary = summarize_positions(capital, normalized)
    equity = float(cash) + float(summary["current_exposure"]) + float(realized_pnl) + float(unrealized_pnl)
    peak = equity if peak_equity is None else float(peak_equity)
    if peak < equity:
        peak = equity
    drawdown = max(0.0, peak - equity)
    drawdown_ratio = drawdown / float(capital) if float(capital) > 0 else 0.0
    return {
        "capital": float(capital),
        "cash": float(cash),
        "positions": list(normalized),
        "position_count": summary["position_count"],
        "current_exposure": summary["current_exposure"],
        "current_exposure_ratio": summary["current_exposure_ratio"],
        "current_risk": summary["current_risk"],
        "current_risk_ratio": summary["current_risk_ratio"],
        "realized_pnl": float(realized_pnl),
        "unrealized_pnl": float(unrealized_pnl),
        "equity": round(equity, 2),
        "peak_equity": round(peak, 2),
        "drawdown": round(drawdown, 2),
        "drawdown_ratio": round(drawdown_ratio, 6),
        "scaling_mode": "DYNAMIC_PERCENTAGE_BASED",
    }
