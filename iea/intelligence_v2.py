from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable


FACTOR_NAMES = (
    "fundamental",
    "trend",
    "volume",
    "liquidity",
    "sentiment",
    "news_risk",
    "open_interest",
    "funding_rate",
)


@dataclass(frozen=True)
class FactorResult:
    name: str
    status: str
    score: float | None = None
    confidence: float | None = None
    provider: str | None = None
    timestamp: str | None = None
    details: dict[str, Any] | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "status": self.status,
            "score": self.score,
            "confidence": self.confidence,
            "provider": self.provider,
            "timestamp": self.timestamp,
            "details": self.details or {},
        }


FactorAdapter = Callable[[Any], FactorResult]


class FactorRegistry:
    """Deterministic registry for the eight-factor intelligence layer."""

    def __init__(self) -> None:
        self._adapters: dict[str, FactorAdapter] = {}

    def register(self, name: str, adapter: FactorAdapter) -> None:
        if name not in FACTOR_NAMES:
            raise ValueError(f"Unknown factor: {name}")
        self._adapters[name] = adapter

    def evaluate(self, context: Any) -> list[FactorResult]:
        results: list[FactorResult] = []
        for name in FACTOR_NAMES:
            adapter = self._adapters.get(name)
            if adapter is None:
                results.append(FactorResult(name=name, status="UNAVAILABLE"))
                continue
            result = adapter(context)
            if result.name != name:
                raise ValueError(f"Adapter returned {result.name!r} for {name!r}")
            results.append(result)
        return results


def _confidence_weight(result: FactorResult) -> float:
    """Return a safe aggregation weight in the inclusive range [0, 1]."""
    if result.confidence is None:
        return 1.0
    try:
        return max(0.0, min(1.0, float(result.confidence)))
    except (TypeError, ValueError):
        return 0.0


def aggregate(results: list[FactorResult], minimum_coverage: float = 0.5) -> dict[str, Any]:
    available = [r for r in results if r.score is not None and r.status == "OK"]
    unavailable = [r.name for r in results if r not in available]
    coverage = len(available) / len(FACTOR_NAMES)
    base = {
        "coverage": round(coverage, 3),
        "available_factors": [r.name for r in available],
        "unavailable_factors": unavailable,
    }

    if not available or coverage < minimum_coverage:
        return {
            "score": None,
            "regime": "INSUFFICIENT_DATA",
            **base,
        }

    weighted = [(r, _confidence_weight(r)) for r in available]
    total_weight = sum(weight for _, weight in weighted)
    if total_weight <= 0:
        return {
            "score": None,
            "regime": "INSUFFICIENT_DATA",
            **base,
        }

    factor_weights = {
        result.name: round(weight / total_weight, 3)
        for result, weight in weighted
    }
    contributions = {
        result.name: round(result.score * weight / total_weight, 2)
        for result, weight in weighted
    }
    score = round(sum(contributions.values()), 2)
    if score >= 62.5:
        regime = "RISK_ON"
    elif score <= 37.5:
        regime = "RISK_OFF"
    else:
        regime = "NEUTRAL"
    return {
        "score": score,
        "regime": regime,
        "factor_weights": factor_weights,
        "factor_contributions": contributions,
        **base,
    }
