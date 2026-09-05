from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .confidence import clamp_confidence, combine_confidence, coverage_confidence, freshness_confidence, sample_confidence
from .decision import build_decision
from .intelligence import analyze
from .intelligence_v2 import FactorRegistry, FactorResult, aggregate
from .iran_market import IranMarketAdapter, iran_factor_adapters
from .market_adapters import ResilientMarketAdapter, crypto_factor_adapters
from .news import GDELTNewsAdapter, news_risk_factor
from .sentiment import AlternativeFearGreedAdapter, sentiment_factor

_PROVIDER_BASE_CONFIDENCE = {
    "FRED": 0.95,
    "BINANCE_FUTURES": 0.98,
    "BYBIT_LINEAR": 0.94,
    "OKX_SWAP": 0.90,
    "ALTERNATIVE_ME": 0.85,
    "GDELT": 0.80,
    "TSETMC_CDN": 0.85,
}

_FACTOR_MAX_AGE_HOURS = {
    "fundamental": 24 * 30,
    "trend": 24,
    "volume": 24,
    "liquidity": 1,
    "sentiment": 48,
    "news_risk": 8,
    "open_interest": 2,
    "funding_rate": 2,
}

_FACTOR_REQUIRED_FIELDS = {
    "trend": ("return_4h_pct", "return_24h_pct"),
    "volume": ("relative_volume_1h",),
    "liquidity": ("bid_depth_usd", "ask_depth_usd", "depth_imbalance"),
    "open_interest": ("open_interest", "previous_open_interest", "oi_change_pct_1h"),
    "funding_rate": ("funding_rate_pct", "funding_regime"),
    "sentiment": ("value", "classification"),
}

_FACTOR_SAMPLE_TARGETS = {
    "trend": 25,
    "volume": 25,
    "liquidity": 20,
    "open_interest": 2,
    "funding_rate": 1,
}


def _dynamic_confidence(result: FactorResult) -> float:
    """Derive factor confidence from provider, freshness, completeness, and sample depth."""
    if result.status != "OK":
        return 0.0
    details = result.details or {}
    provider_quality = _PROVIDER_BASE_CONFIDENCE.get(result.provider or "", 0.70)
    quality_signals = [provider_quality]
    if result.timestamp:
        quality_signals.append(freshness_confidence(result.timestamp, max_age_hours=_FACTOR_MAX_AGE_HOURS.get(result.name, 24)))
    required = _FACTOR_REQUIRED_FIELDS.get(result.name)
    if required:
        alternatives = {"trend": (("return_4h_pct", "return_24h_pct"), ("return_1d_pct", "return_20d_pct")),
                        "volume": (("relative_volume_1h",), ("market_volume", "breadth_up_pct", "breadth_down_pct"))}.get(result.name, (required,))
        best_present = 0
        best_target = len(required)
        for candidate in alternatives:
            present = sum(details.get(field) is not None for field in candidate)
            if present > best_present:
                best_present = present
                best_target = len(candidate)
        quality_signals.append(sample_confidence(best_present, target=best_target))
    sample_target = _FACTOR_SAMPLE_TARGETS.get(result.name)
    if sample_target is not None and "sample_count" in details:
        quality_signals.append(sample_confidence(details["sample_count"], target=sample_target))
    if "coverage" in details:
        quality_signals.append(coverage_confidence(details["coverage"]))
    if "article_count" in details:
        quality_signals.append(sample_confidence(details["article_count"], target=10))
    return round(combine_confidence(*quality_signals), 3)


def _fundamental_adapter(store: Any) -> FactorResult:
    report = analyze(store)
    if report["score"] is None:
        return FactorResult(name="fundamental", status="UNAVAILABLE", provider="FRED")
    return FactorResult(name="fundamental", status="OK", score=report["score"], confidence=report["coverage"],
                        provider="FRED", timestamp=report["generated_at"],
                        details={"engine": report["engine"], "macro_regime": report["regime"], "coverage": report["coverage"]})


def analyze_eight_factor(
    store: Any,
    market_adapter: Any | None = None,
    sentiment_adapter: AlternativeFearGreedAdapter | None = None,
    news_adapter: GDELTNewsAdapter | None = None,
    capital: float | None = None,
) -> dict[str, Any]:
    registry = FactorRegistry()
    registry.register("fundamental", _fundamental_adapter)
    region = __import__("os").getenv("IEA_MARKET_REGION", "IRAN").strip().upper()
    if market_adapter is not None:
        market = market_adapter
        trend, volume, liquidity, open_interest, funding_rate = crypto_factor_adapters(market)
    elif region in {"IR", "IRAN", "TSE", "TSETMC"}:
        market = IranMarketAdapter()
        trend, volume, liquidity, open_interest, funding_rate = iran_factor_adapters(market)
    else:
        market = ResilientMarketAdapter()
        trend, volume, liquidity, open_interest, funding_rate = crypto_factor_adapters(market)
    registry.register("trend", trend)
    registry.register("volume", volume)
    registry.register("liquidity", liquidity)
    registry.register("open_interest", open_interest)
    registry.register("funding_rate", funding_rate)
    registry.register("sentiment", sentiment_factor(sentiment_adapter))
    registry.register("news_risk", news_risk_factor(news_adapter))
    raw_results = registry.evaluate(store)
    results = [FactorResult(name=result.name, status=result.status, score=result.score,
                            confidence=_dynamic_confidence(result), provider=result.provider,
                            timestamp=result.timestamp, details=result.details) for result in raw_results]
    summary = aggregate(results)
    factor_dicts = [result.as_dict() for result in results]
    decision_input = {**summary, "factors": factor_dicts}
    if capital is not None:
        decision_input["capital"] = capital
    decision = build_decision(decision_input)
    market_status = None
    session_date = None
    if hasattr(market, "session_state"):
        market_status, session_date = market.session_state()
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "eight_factor_market_intelligence_v2",
        "symbol": getattr(market, "symbol", "UNKNOWN"),
        "market_region": region,
        "market_status": market_status,
        "session_date": session_date,
        **summary,
        "decision": decision,
        "factors": factor_dicts,
    }
