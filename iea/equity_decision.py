from __future__ import annotations

from typing import Any

from .decision import build_decision
from .equity_analysis import EquityAnalysis


DEFAULT_EQUITY_WEIGHT = 0.40
DEFAULT_MARKET_WEIGHT = 0.60


def _regime_from_score(score: float) -> str:
    if score >= 62.5:
        return "RISK_ON"
    if score <= 37.5:
        return "RISK_OFF"
    return "NEUTRAL"


def build_equity_market_decision(
    analysis: EquityAnalysis,
    market_report: dict[str, Any],
    equity_weight: float = DEFAULT_EQUITY_WEIGHT,
    market_weight: float = DEFAULT_MARKET_WEIGHT,
) -> dict[str, Any]:
    """Combine asset-level equity analysis with the eight-factor market view.

    The equity layer supplies fundamental quality plus valuation; the market layer
    supplies regime, coverage, and risk flags. The existing decision engine remains
    the final policy gate, so this function never executes a trade.
    """
    if equity_weight < 0 or market_weight < 0:
        raise ValueError("weights must be non-negative")
    total = equity_weight + market_weight
    if total <= 0:
        raise ValueError("at least one decision weight must be positive")

    equity_weight /= total
    market_weight /= total

    market_score = market_report.get("score")
    if market_score is None:
        combined_score = None
        coverage = 0.0
        regime = "INSUFFICIENT_DATA"
    else:
        combined_score = round(
            equity_weight * float(analysis.final_score)
            + market_weight * float(market_score),
            2,
        )
        market_coverage = float(market_report.get("coverage") or 0.0)
        coverage = round(min(1.0, market_coverage), 3)
        regime = _regime_from_score(combined_score)

    decision_input = {
        **market_report,
        "score": combined_score,
        "coverage": coverage,
        "regime": regime,
        "factors": market_report.get("factors") or [],
    }
    decision = build_decision(decision_input)

    return {
        "symbol": analysis.symbol,
        "equity_score": analysis.final_score,
        "market_score": market_score,
        "combined_score": combined_score,
        "equity_weight": round(equity_weight, 3),
        "market_weight": round(market_weight, 3),
        "coverage": coverage,
        "regime": regime,
        "equity_signal": analysis.final_signal,
        "decision": decision,
    }
