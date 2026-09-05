from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class StockSnapshot:
    symbol: str
    price: float
    volume: float = 0.0
    market_cap: float | None = None
    eps: float | None = None
    sector: str | None = None


@dataclass(frozen=True)
class StockScore:
    symbol: str
    score: float
    valuation_signal: str
    quality_signal: str
    reasons: tuple[str, ...]


def _positive(value: float, name: str) -> float:
    number = float(value)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def score_stock(
    snapshot: StockSnapshot,
    fair_value: float | None = None,
    quality_score: float = 0.5,
) -> StockScore:
    """Create an advisory stock score from validated market/fundamental inputs."""
    price = _positive(snapshot.price, "price")
    quality = float(quality_score)
    if not 0 <= quality <= 1:
        raise ValueError("quality_score must be between 0 and 1")

    score = 50.0
    reasons: list[str] = []
    if fair_value is not None:
        value = _positive(fair_value, "fair_value")
        upside = value / price - 1.0
        score += max(-25.0, min(25.0, upside * 100.0))
        if upside >= 0.20:
            valuation_signal = "UNDERVALUED"
            reasons.append("fair value implies at least 20% upside")
        elif upside <= -0.15:
            valuation_signal = "OVERVALUED"
            reasons.append("fair value implies at least 15% downside")
        else:
            valuation_signal = "FAIR"
            reasons.append("fair value is near market price")
    else:
        valuation_signal = "UNAVAILABLE"
        score -= 10.0
        reasons.append("valuation input unavailable")

    score += (quality - 0.5) * 40.0
    quality_signal = "STRONG" if quality >= 0.7 else "WEAK" if quality < 0.3 else "NEUTRAL"
    reasons.append(f"fundamental quality score={quality:.2f}")
    return StockScore(
        symbol=str(snapshot.symbol).upper(),
        score=round(max(0.0, min(100.0, score)), 2),
        valuation_signal=valuation_signal,
        quality_signal=quality_signal,
        reasons=tuple(reasons),
    )


def rank_stocks(scores: Iterable[StockScore]) -> tuple[StockScore, ...]:
    """Rank stocks from strongest to weakest advisory score."""
    return tuple(sorted(scores, key=lambda item: item.score, reverse=True))


def stock_market_summary(scores: Iterable[StockScore]) -> dict[str, object]:
    ranked = rank_stocks(scores)
    return {
        "universe_size": len(ranked),
        "ranked_symbols": [item.symbol for item in ranked],
        "top_candidates": [
            {
                "symbol": item.symbol,
                "score": item.score,
                "valuation_signal": item.valuation_signal,
                "quality_signal": item.quality_signal,
                "reasons": list(item.reasons),
            }
            for item in ranked[:10]
        ],
    }
