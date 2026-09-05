from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable


@dataclass(frozen=True)
class CapitalObservation:
    """Normalized observation describing where an institution is allocating capital."""

    institution: str
    institution_type: str
    country: str
    asset: str
    action: str
    value: float | None = None
    currency: str | None = None
    date: str | None = None
    source: str | None = None
    reason: str | None = None
    confidence: float = 0.5


@dataclass(frozen=True)
class CapitalSignal:
    """Aggregated advisory signal for a capital-allocation theme."""

    asset: str
    score: float
    direction: str
    observation_count: int
    confidence: float
    reasons: tuple[str, ...]


def _normalize_action(action: str) -> str:
    normalized = str(action).strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "BUY": "BUY",
        "PURCHASE": "BUY",
        "PURCHASES": "BUY",
        "ACCUMULATION": "BUY",
        "ACCUMULATE": "BUY",
        "SELL": "SELL",
        "SALES": "SELL",
        "REDUCTION": "SELL",
        "REDUCE": "SELL",
        "HOLD": "HOLD",
        "NEUTRAL": "HOLD",
    }
    return aliases.get(normalized, normalized)


def score_capital_observations(
    observations: Iterable[CapitalObservation],
) -> tuple[CapitalSignal, ...]:
    """Aggregate normalized capital-allocation observations by asset.

    Positive scores indicate net accumulation, negative scores indicate net
    reduction. The function is source-agnostic so official data, filings and
    high-quality research feeds can be added without changing the signal layer.
    """
    buckets: dict[str, list[CapitalObservation]] = {}
    for observation in observations:
        if observation.confidence < 0 or observation.confidence > 1:
            raise ValueError("confidence must be between 0 and 1")
        asset = str(observation.asset).strip().upper()
        if not asset:
            raise ValueError("asset must not be empty")
        buckets.setdefault(asset, []).append(observation)

    signals: list[CapitalSignal] = []
    for asset, items in buckets.items():
        score = 0.0
        weighted_reasons: list[str] = []
        confidence_mass = 0.0
        for item in items:
            action = _normalize_action(item.action)
            weight = max(float(item.confidence), 0.0)
            if action == "BUY":
                score += weight
            elif action == "SELL":
                score -= weight
            elif action != "HOLD":
                continue
            confidence_mass += weight
            if item.reason:
                weighted_reasons.append(item.reason)

        if score > 0:
            direction = "ACCUMULATION"
        elif score < 0:
            direction = "REDUCTION"
        else:
            direction = "NEUTRAL"

        confidence = min(1.0, confidence_mass / max(len(items), 1))
        signals.append(
            CapitalSignal(
                asset=asset,
                score=round(score, 4),
                direction=direction,
                observation_count=len(items),
                confidence=round(confidence, 4),
                reasons=tuple(weighted_reasons),
            )
        )

    return tuple(sorted(signals, key=lambda signal: abs(signal.score), reverse=True))


def central_bank_watchlist() -> tuple[str, ...]:
    """Core central banks to monitor for reserve and policy-allocation signals."""
    return (
        "Federal Reserve",
        "European Central Bank",
        "People's Bank of China",
        "Bank of Japan",
        "Bank of England",
        "Swiss National Bank",
        "Reserve Bank of India",
        "Bank of Canada",
        "Reserve Bank of Australia",
        "Central Bank of Russia",
        "Central Bank of Türkiye",
        "Central Bank of the Republic of Iran",
    )
