from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

import requests

from ..market_intelligence import MarketSnapshot

DEFAULT_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (1, 3)


class YahooChartProvider:
    """Fetch live-ish market snapshots from Yahoo Finance chart data.

    The provider is deliberately small and dependency-free. Symbols are
    supplied by configuration so Iran-market adapters can be added without
    changing the normalized analysis layer.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = base_url or os.getenv("IEA_MARKET_DATA_URL", DEFAULT_URL)
        self.timeout = timeout

    def snapshot(self, symbol: str) -> MarketSnapshot:
        if not symbol or not symbol.strip():
            raise ValueError("market symbol is required")

        url = self.base_url.format(symbol=symbol.strip())
        params = {"range": "1d", "interval": "1m", "includePrePost": "true"}
        response = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            response = requests.get(url, params=params, timeout=self.timeout)
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == MAX_ATTEMPTS:
                break
            time.sleep(RETRY_DELAYS_SECONDS[attempt - 1])
        response.raise_for_status()

        payload = response.json()
        result = ((payload.get("chart") or {}).get("result") or [None])[0]
        if not result:
            raise ValueError(f"no market data returned for {symbol}")

        meta: dict[str, Any] = result.get("meta") or {}
        price = meta.get("regularMarketPrice")
        if price is None:
            raise ValueError(f"market price missing for {symbol}")

        observed_epoch = meta.get("regularMarketTime")
        if observed_epoch is None:
            timestamps = result.get("timestamp") or []
            observed_epoch = timestamps[-1] if timestamps else None
        if observed_epoch is None:
            raise ValueError(f"market timestamp missing for {symbol}")

        quote = ((result.get("indicators") or {}).get("quote") or [None])[0] or {}
        volume_values = quote.get("volume") or []
        high_values = quote.get("high") or []
        low_values = quote.get("low") or []

        return MarketSnapshot(
            symbol=symbol.strip(),
            observed_at=datetime.fromtimestamp(float(observed_epoch), tz=timezone.utc),
            price=float(price),
            previous_close=_optional_float(meta.get("previousClose")),
            volume=_last_float(volume_values),
            average_volume=_optional_float(meta.get("averageDailyVolume3Month")),
            high=_last_float(high_values),
            low=_last_float(low_values),
            source="yahoo_chart",
        )

    def snapshots(self, symbols: list[str] | tuple[str, ...]) -> list[MarketSnapshot]:
        return [self.snapshot(symbol) for symbol in symbols]


def configured_symbols() -> list[str]:
    raw = os.getenv("IEA_MARKET_SYMBOLS", "").strip()
    return [item.strip() for item in raw.split(",") if item.strip()]


def _optional_float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _last_float(values: Any) -> float | None:
    if not values:
        return None
    for value in reversed(values):
        converted = _optional_float(value)
        if converted is not None:
            return converted
    return None
