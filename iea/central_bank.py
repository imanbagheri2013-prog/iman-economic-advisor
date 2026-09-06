"""Iran central-bank intelligence layer.

This module normalizes monetary and policy observations so the advisor can
track the Central Bank of Iran without coupling the intelligence engine to a
single upstream website or undocumented endpoint.

The production ingestion layer should populate observations from official
CBI releases/data first, then approved fallback datasets when an official
observation is unavailable. No value is fabricated here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, Iterable


CBI_SOURCE = "CBI"

# Core monetary indicators. The list intentionally separates stocks, growth
# rates and policy instruments so the advisor can distinguish "money exists"
# from "money is being created faster".
MONETARY_INDICATORS = (
    "monetary_base",
    "liquidity_m2",
    "m1",
    "quasi_money",
    "currency_in_circulation",
    "bank_deposits",
    "bank_credit",
    "central_bank_credit_to_banks",
    "government_claims_on_central_bank",
    "bank_reserves",
    "reserve_requirement",
    "policy_rate",
    "interbank_rate",
    "open_market_operations",
    "government_deposits",
    "net_foreign_assets",
    "foreign_exchange_reserves",
)

POLICY_EVENT_TYPES = (
    "rate_change",
    "reserve_requirement_change",
    "open_market_operation",
    "credit_facility_change",
    "fx_policy_change",
    "regulatory_change",
    "liquidity_injection",
    "liquidity_absorption",
    "official_statement",
)


@dataclass(frozen=True)
class MonetaryObservation:
    indicator: str
    value: float
    unit: str
    observed_at: str
    source: str = CBI_SOURCE
    frequency: str | None = None
    source_url: str | None = None
    revision: bool = False
    metadata: dict[str, Any] | None = None


@dataclass(frozen=True)
class PolicyEvent:
    event_type: str
    announced_at: str
    title: str
    direction: str | None = None
    magnitude: float | None = None
    unit: str | None = None
    source: str = CBI_SOURCE
    source_url: str | None = None
    details: dict[str, Any] | None = None


def _require_indicator(indicator: str) -> str:
    normalized = indicator.strip().lower()
    if normalized not in MONETARY_INDICATORS:
        raise ValueError(f"Unknown CBI monetary indicator: {indicator}")
    return normalized


def normalize_observation(
    indicator: str,
    value: float,
    unit: str,
    observed_at: str | datetime,
    *,
    frequency: str | None = None,
    source: str = CBI_SOURCE,
    source_url: str | None = None,
    revision: bool = False,
    metadata: dict[str, Any] | None = None,
) -> MonetaryObservation:
    """Validate and normalize one monetary observation."""
    name = _require_indicator(indicator)
    if isinstance(observed_at, datetime):
        timestamp = observed_at.isoformat()
    else:
        timestamp = str(observed_at)
    numeric_value = float(value)
    if not unit:
        raise ValueError("unit is required")
    return MonetaryObservation(
        indicator=name,
        value=numeric_value,
        unit=unit,
        observed_at=timestamp,
        source=source,
        frequency=frequency,
        source_url=source_url,
        revision=revision,
        metadata=metadata or {},
    )


def growth_rate(current: float, previous: float) -> float | None:
    """Calculate period-over-period percentage growth without inventing a base."""
    if previous == 0:
        return None
    return round((float(current) / float(previous) - 1.0) * 100.0, 4)


def build_monetary_dashboard(observations: Iterable[MonetaryObservation]) -> dict[str, Any]:
    """Create a compact dashboard for the advisor's macro decision layer."""
    latest: dict[str, MonetaryObservation] = {}
    revisions = 0
    for observation in observations:
        _require_indicator(observation.indicator)
        current = latest.get(observation.indicator)
        if current is None or observation.observed_at >= current.observed_at:
            latest[observation.indicator] = observation
        revisions += int(observation.revision)

    values = {
        name: {
            "value": item.value,
            "unit": item.unit,
            "observed_at": item.observed_at,
            "source": item.source,
            "frequency": item.frequency,
            "source_url": item.source_url,
        }
        for name, item in latest.items()
    }

    return {
        "source": CBI_SOURCE,
        "indicator_count": len(latest),
        "available_indicators": sorted(latest),
        "missing_indicators": sorted(set(MONETARY_INDICATORS) - set(latest)),
        "revision_count": revisions,
        "indicators": values,
    }


def classify_monetary_impulse(
    *,
    monetary_base_growth: float | None,
    liquidity_growth: float | None,
    bank_credit_growth: float | None = None,
) -> dict[str, Any]:
    """Classify the direction of monetary impulse from observed growth rates.

    This is deliberately a transparent rule, not a claim about causality.
    It gives the advisor a signal that can later be combined with inflation,
    FX and real-economy data.
    """
    growths = [x for x in (monetary_base_growth, liquidity_growth) if x is not None]
    if not growths:
        return {"status": "INSUFFICIENT_DATA", "direction": "UNKNOWN", "score": None}

    average = sum(growths) / len(growths)
    credit = bank_credit_growth if bank_credit_growth is not None else average
    if average >= 30 and credit >= 20:
        direction = "STRONG_EXPANSION"
    elif average >= 15:
        direction = "EXPANSION"
    elif average <= 5 and credit <= 10:
        direction = "CONTRACTIONARY_OR_TIGHT"
    else:
        direction = "MIXED"

    return {
        "status": "OK",
        "direction": direction,
        "score": round(average, 2),
        "monetary_base_growth": monetary_base_growth,
        "liquidity_growth": liquidity_growth,
        "bank_credit_growth": bank_credit_growth,
    }


def summarize_policy_event(event: PolicyEvent) -> dict[str, Any]:
    """Convert a CBI policy event into an advisor-friendly risk signal."""
    if event.event_type not in POLICY_EVENT_TYPES:
        raise ValueError(f"Unknown CBI policy event type: {event.event_type}")
    return {
        "event_type": event.event_type,
        "announced_at": event.announced_at,
        "title": event.title,
        "direction": event.direction,
        "magnitude": event.magnitude,
        "unit": event.unit,
        "source": event.source,
        "source_url": event.source_url,
        "details": event.details or {},
    }
