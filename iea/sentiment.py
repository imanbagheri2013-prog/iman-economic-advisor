from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests


FEAR_GREED_API = "https://api.alternative.me/fng/"


class AlternativeFearGreedAdapter:
    """Read the latest crypto Fear & Greed Index from Alternative.me."""

    def __init__(self, timeout: float = 10.0) -> None:
        self.timeout = timeout

    def snapshot(self) -> dict[str, Any]:
        response = requests.get(
            FEAR_GREED_API,
            params={"limit": 2},
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data", []) if isinstance(payload, dict) else []
        if not rows:
            raise ValueError("Fear & Greed API returned no data")

        latest = rows[0]
        previous = rows[1] if len(rows) > 1 else None
        value = float(latest["value"])
        if not 0.0 <= value <= 100.0:
            raise ValueError("Fear & Greed value is outside 0-100")

        timestamp = latest.get("timestamp")
        generated_at = datetime.fromtimestamp(int(timestamp), tz=timezone.utc).isoformat() if timestamp else None
        previous_value = float(previous["value"]) if previous and previous.get("value") is not None else None
        change = value - previous_value if previous_value is not None else None

        return {
            "value": value,
            "classification": str(latest.get("value_classification", "Unknown")),
            "previous_value": previous_value,
            "change": change,
            "timestamp": generated_at,
        }


def sentiment_factor(adapter: AlternativeFearGreedAdapter | None = None):
    """Return an eight-factor adapter backed by the crypto Fear & Greed Index."""
    source = adapter or AlternativeFearGreedAdapter()

    def evaluate(_: Any):
        from .intelligence_v2 import FactorResult

        try:
            snapshot = source.snapshot()
        except (requests.RequestException, ValueError, KeyError, TypeError, OSError):
            return FactorResult("sentiment", "UNAVAILABLE", provider="ALTERNATIVE_ME")

        value = float(snapshot["value"])
        return FactorResult(
            "sentiment",
            "OK",
            round(value, 2),
            0.85,
            "ALTERNATIVE_ME",
            snapshot.get("timestamp"),
            details={
                "index": "CRYPTO_FEAR_GREED",
                "value": round(value, 2),
                "classification": snapshot.get("classification"),
                "previous_value": snapshot.get("previous_value"),
                "change_1d": snapshot.get("change"),
                "source": "Alternative.me",
            },
        )

    return evaluate
