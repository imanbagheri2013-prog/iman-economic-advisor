from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Iterable

from .equity_fundamentals import FundamentalSnapshot, FundamentalQuality, score_fundamentals
from .equity_valuation import EquityValuation, build_equity_valuation, valuation_summary


@dataclass(frozen=True)
class EquityAnalysis:
    symbol: str
    fundamental: FundamentalQuality
    valuation: EquityValuation
    final_score: float
    final_signal: str
    reasons: tuple[str, ...]


def _valuation_score(valuation: EquityValuation) -> float:
    upside = (valuation.intrinsic_value / valuation.current_price) - 1.0
    return max(0.0, min(100.0, 50.0 + upside * 100.0))


def analyze_equity(
    snapshot: FundamentalSnapshot,
    current_price: float,
    method_values: Iterable[float],
    method_weights: Iterable[float],
    confidence: float = 0.7,
    downside: float = 0.20,
    upside: float = 0.25,
    methods_used: Iterable[str] = ("weighted_valuation",),
) -> EquityAnalysis:
    """Combine fundamental quality and intrinsic valuation into one advisory view."""
    fundamental = score_fundamentals(snapshot)
    valuation = build_equity_valuation(
        symbol=snapshot.symbol,
        current_price=current_price,
        method_values=method_values,
        method_weights=method_weights,
        confidence=confidence,
        downside=downside,
        upside=upside,
        methods_used=methods_used,
    )

    valuation_score = _valuation_score(valuation)
    final_score = round(0.60 * fundamental.score + 0.40 * valuation_score, 2)

    if final_score >= 70:
        final_signal = "ATTRACTIVE"
    elif final_score < 40:
        final_signal = "UNATTRACTIVE"
    else:
        final_signal = "NEUTRAL"

    reasons = list(fundamental.reasons)
    valuation_upside = (valuation.intrinsic_value / valuation.current_price - 1.0) * 100.0
    if valuation_upside >= 15:
        reasons.append("material upside to intrinsic value")
    elif valuation_upside <= -15:
        reasons.append("material downside to intrinsic value")
    else:
        reasons.append("valuation close to current price")

    return EquityAnalysis(
        symbol=str(snapshot.symbol).upper(),
        fundamental=fundamental,
        valuation=valuation,
        final_score=final_score,
        final_signal=final_signal,
        reasons=tuple(reasons),
    )


def equity_analysis_summary(analysis: EquityAnalysis) -> dict[str, object]:
    """Serialize the unified equity analysis for reports and downstream APIs."""
    return {
        "symbol": analysis.symbol,
        "fundamental": {
            "score": analysis.fundamental.score,
            "signal": analysis.fundamental.signal,
            "metrics": asdict(analysis.fundamental.metrics),
            "reasons": list(analysis.fundamental.reasons),
        },
        "valuation": valuation_summary(analysis.valuation),
        "final_score": analysis.final_score,
        "final_signal": analysis.final_signal,
        "reasons": list(analysis.reasons),
    }
