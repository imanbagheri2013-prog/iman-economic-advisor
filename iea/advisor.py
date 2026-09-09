from __future__ import annotations

from typing import Any, Iterable

from .capital_allocation import build_capital_allocation
from .equity_analysis import FundamentalSnapshot, analyze_equity, equity_analysis_summary
from .equity_decision import build_equity_market_decision
from .live_decision import apply_live_market_overlay
from .market_intelligence import analyze_snapshots
from .providers.market import YahooChartProvider, configured_symbols


def _configured_live_market_intelligence() -> dict[str, Any] | None:
    symbols = configured_symbols()
    if not symbols:
        return None
    provider = YahooChartProvider()
    snapshots = []
    errors = []
    for symbol in symbols:
        try:
            snapshots.append(provider.snapshot(symbol))
        except Exception as exc:
            errors.append({"symbol": symbol, "error_type": type(exc).__name__, "error": str(exc)})
    report = analyze_snapshots(snapshots)
    report["status"] = "OK" if snapshots else "NO_DATA"
    report["requested_symbols"] = symbols
    report["provider"] = "yahoo_chart"
    if errors:
        report["errors"] = errors
    return report


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

    Configured live market data is automatically used when an explicit report
    is not supplied. Stale, missing, or disagreeing live data fails closed to
    NO_TRADE through the live decision overlay, and capital allocation is
    allowed only after the final BUY/SELL gate passes.
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
    live_report = live_market_intelligence
    if live_report is None:
        live_report = _configured_live_market_intelligence()
    decision = apply_live_market_overlay(
        unified["decision"],
        live_report,
        symbol=analysis.symbol,
    )
    decision, capital_allocation = build_capital_allocation(decision)

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
        "capital_allocation": capital_allocation,
        "combined_score": unified["combined_score"],
        "weights": {
            "equity": unified["equity_weight"],
            "market": unified["market_weight"],
        },
        "live_market": live_report,
    }
