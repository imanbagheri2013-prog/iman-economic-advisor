from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def clamp_confidence(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def freshness_confidence(timestamp: str | None, *, max_age_hours: float) -> float:
    """Convert data age into a bounded confidence score."""
    if not timestamp or max_age_hours <= 0:
        return 0.0
    try:
        observed = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        age_hours = max(0.0, (datetime.now(timezone.utc) - observed).total_seconds() / 3600.0)
    except (TypeError, ValueError):
        return 0.0
    return clamp_confidence(1.0 - age_hours / max_age_hours)


def coverage_confidence(coverage: Any) -> float:
    """Normalize a source coverage metric into confidence."""
    try:
        return clamp_confidence(float(coverage))
    except (TypeError, ValueError):
        return 0.0


def sample_confidence(count: Any, *, target: float) -> float:
    """Increase confidence smoothly as the number of observations approaches target."""
    if target <= 0:
        return 0.0
    try:
        value = max(0.0, float(count))
    except (TypeError, ValueError):
        return 0.0
    return clamp_confidence(value / target)


def combine_confidence(*values: float) -> float:
    """Combine independent quality signals conservatively using their geometric mean."""
    if not values:
        return 0.0
    normalized = [clamp_confidence(value) for value in values]
    if any(value == 0.0 for value in normalized):
        return 0.0
    product = 1.0
    for value in normalized:
        product *= value
    return clamp_confidence(product ** (1.0 / len(normalized)))
