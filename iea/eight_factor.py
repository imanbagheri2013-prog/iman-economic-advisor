from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .intelligence import analyze
from .intelligence_v2 import FactorRegistry, FactorResult, aggregate


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


def analyze_eight_factor(store: Any) -> dict[str, Any]:
    registry = FactorRegistry()
    registry.register("fundamental", _fundamental_adapter)
    results = registry.evaluate(store)
    summary = aggregate(results)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "eight_factor_market_intelligence_v2",
        **summary,
        "factors": [result.as_dict() for result in results],
    }
