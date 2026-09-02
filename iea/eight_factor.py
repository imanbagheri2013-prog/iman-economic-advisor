from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .intelligence import analyze
from .intelligence_v2 import FactorRegistry, FactorResult, aggregate
from .market_adapters import BinanceMarketAdapter, crypto_factor_adapters
from .sentiment import AlternativeFearGreedAdapter, sentiment_factor


def _fundamental_adapter(store: Any) -> FactorResult:
    report = analyze(store)
    if report["score"] is None:
        return FactorResult(name="fundamental", status="UNAVAILABLE", provider="FRED")
    return FactorResult(
        name="fundamental",
        status="OK",
        score=report["score"],
        confidence=report["coverage"],
        provider="FRED",
        timestamp=report["generated_at"],
        details={"engine": report["engine"], "macro_regime": report["regime"]},
    )


def analyze_eight_factor(
    store: Any,
    market_adapter: BinanceMarketAdapter | None = None,
    sentiment_adapter: AlternativeFearGreedAdapter | None = None,
) -> dict[str, Any]:
    registry = FactorRegistry()
    registry.register("fundamental", _fundamental_adapter)

    market = market_adapter or BinanceMarketAdapter()
    trend, volume, liquidity, open_interest, funding_rate = crypto_factor_adapters(market)
    registry.register("trend", trend)
    registry.register("volume", volume)
    registry.register("liquidity", liquidity)
    registry.register("open_interest", open_interest)
    registry.register("funding_rate", funding_rate)
    registry.register("sentiment", sentiment_factor(sentiment_adapter))

    results = registry.evaluate(store)
    summary = aggregate(results)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "eight_factor_market_intelligence_v2",
        "symbol": market.symbol,
        **summary,
        "factors": [result.as_dict() for result in results],
    }
