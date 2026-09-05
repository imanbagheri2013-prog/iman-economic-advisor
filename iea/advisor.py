from __future__ import annotations

from typing import Any, Iterable

from .equity_analysis import FundamentalSnapshot, analyze_equity
from .equity_decision import build_equity_market_decision


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
) -> dict[str, Any]:
    """Build the end-to-end equity advisory report.

    This is the application-level orchestration layer: it runs the asset-level
    fundamental/valuation analysis and then feeds that result into the unified
    equity + eight-factor market decision engine.
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

    return {
        "engine": "iea_equity_advisor_v1",
        "symbol": analysis.symbol,
        "analysis": {
            "fundamental": analysis.fundamental.to_dict(),
            "valuation": analysis.valuation.to_dict(),
            "final_score": analysis.final_score,
            "final_signal": analysis.final_signal,
            "reasons": list(analysis.reasons),
        },
        "market": {
            "score": unified["market_score"],
            "coverage": unified["coverage"],
            "regime": unified["regime"],
        },
        "decision": unified["decision"],
        "combined_score": unified["combined_score"],
        "weights": {
            "equity": unified["equity_weight"],
            "market": unified["market_weight"],
        },
    }
