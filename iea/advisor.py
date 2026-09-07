from __future__ import annotations

from typing import Any, Iterable

from .equity_analysis import FundamentalSnapshot, analyze_equity, equity_analysis_summary
from .equity_decision import build_equity_market_decision
from .live_decision import apply_live_market_overlay


def build_equity_advisor_report(
    snapshot: FundamentalSnapshot,
    current_price: float,
    method_values: Iterable[float],
    method_weights: Iterable[float],
    market_report: dict[str, Any],
    *,
    confidence: float = 0.7,
    downside: float = 0.20,
    upside: float = 0.25,
    methods_used: Iterable[str] = ("weighted_valuation",),
    equity_weight: float = 0.40,
    market_weight: float = 0.60,
    live_market_intelligence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Build the end-to-end equity advisory report.

    The live-market layer is an explicit final safety validation: configured
    live data can validate the policy decision, while stale, missing, or
    disagreeing live data fails closed to NO_TRADE.
    """
    analysis = analyze_equity(
        snapshot=snapshot,
        current_price=current_price,
        method_values=method_values,
        method_weights=method_weights,
        confidence=confidence,
        downside=downside,
        upside=upside,
        methods_used=methods_used,
    )
    unified = build_equity_market_decision(
        analysis=analysis,
        market_report=market_report,
        equity_weight=equity_weight,
        market_weight=market_weight,
    )
    decision = apply_live_market_overlay(
        unified["decision"],
        live_market_intelligence,
        symbol=analysis.symbol,
    )

    return {
        "engine": "iea_equity_advisor_v1",
        "symbol": analysis.symbol,
        "analysis": equity_analysis_summary(analysis),
        "market": {
            "score": unified["market_score"],
            "coverage": unified["coverage"],
            "regime": unified["regime"],
        },
        "decision": decision,
        "combined_score": unified["combined_score"],
        "weights": {
            "equity": unified["equity_weight"],
            "market": unified["market_weight"],
        },
        "live_market": live_market_intelligence,
    }
