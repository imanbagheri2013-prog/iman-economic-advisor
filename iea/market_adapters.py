from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import requests


BINANCE_FAPI = "https://fapi.binance.com"


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    price: float
    change_pct: float
    volume: float
    quote_volume: float
    bid: float
    ask: float
    open_interest: float
    funding_rate: float
    oi_change_pct: float | None


class BinanceMarketAdapter:
    """Read public Binance USD-M futures market data without credentials."""

    def __init__(self, symbol: str | None = None, timeout: float = 10.0) -> None:
        self.symbol = (symbol or os.getenv("IEA_MARKET_SYMBOL", "BTCUSDT")).upper()
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, Any]) -> Any:
        response = requests.get(f"{BINANCE_FAPI}{path}", params=params, timeout=self.timeout)
        response.raise_for_status()
        return response.json()

    def snapshot(self) -> MarketSnapshot:
        ticker = self._get("/fapi/v1/ticker/24hr", {"symbol": self.symbol})
        book = self._get("/fapi/v1/ticker/bookTicker", {"symbol": self.symbol})
        oi = self._get("/fapi/v1/openInterest", {"symbol": self.symbol})
        funding = self._get("/fapi/v1/premiumIndex", {"symbol": self.symbol})

        oi_hist = self._get(
            "/futures/data/openInterestHist",
            {"symbol": self.symbol, "period": "1h", "limit": 2},
        )
        current_oi = float(oi["openInterest"])
        previous_oi = float(oi_hist[0]["sumOpenInterest"]) if oi_hist else current_oi
        oi_change = None if previous_oi == 0 else (current_oi / previous_oi - 1.0) * 100.0

        return MarketSnapshot(
            symbol=self.symbol,
            price=float(ticker["lastPrice"]),
            change_pct=float(ticker["priceChangePercent"]),
            volume=float(ticker["volume"]),
            quote_volume=float(ticker["quoteVolume"]),
            bid=float(book["bidPrice"]),
            ask=float(book["askPrice"]),
            open_interest=current_oi,
            funding_rate=float(funding["lastFundingRate"]),
            oi_change_pct=oi_change,
        )


def _bounded(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 2)


def crypto_factor_adapters(adapter: BinanceMarketAdapter):
    # Fetch once so all five crypto factors use the same market snapshot.
    snap = adapter.snapshot()

    def trend(_: Any):
        from .intelligence_v2 import FactorResult
        return FactorResult("trend", "OK", _bounded(50.0 + snap.change_pct * 3.0), 0.9, "BINANCE_FUTURES", details={"symbol": snap.symbol, "change_pct": snap.change_pct})

    def volume(_: Any):
        from .intelligence_v2 import FactorResult
        direction = 10.0 if snap.change_pct > 0 else -10.0 if snap.change_pct < 0 else 0.0
        return FactorResult("volume", "OK", _bounded(50.0 + direction), 0.75, "BINANCE_FUTURES", details={"symbol": snap.symbol, "quote_volume_24h": snap.quote_volume})

    def liquidity(_: Any):
        from .intelligence_v2 import FactorResult
        mid = (snap.bid + snap.ask) / 2.0
        spread_bps = 0.0 if mid == 0 else (snap.ask - snap.bid) / mid * 10000.0
        return FactorResult("liquidity", "OK", _bounded(100.0 - spread_bps * 10.0), 0.8, "BINANCE_FUTURES", details={"symbol": snap.symbol, "spread_bps": round(spread_bps, 4)})

    def open_interest(_: Any):
        from .intelligence_v2 import FactorResult
        if snap.oi_change_pct is None:
            return FactorResult("open_interest", "UNAVAILABLE", provider="BINANCE_FUTURES")
        return FactorResult("open_interest", "OK", _bounded(50.0 + snap.oi_change_pct * 5.0), 0.8, "BINANCE_FUTURES", details={"symbol": snap.symbol, "oi_change_pct_1h": snap.oi_change_pct})

    def funding_rate(_: Any):
        from .intelligence_v2 import FactorResult
        return FactorResult("funding_rate", "OK", _bounded(50.0 - snap.funding_rate * 10000.0), 0.8, "BINANCE_FUTURES", details={"symbol": snap.symbol, "funding_rate": snap.funding_rate})

    return trend, volume, liquidity, open_interest, funding_rate
