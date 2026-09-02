from __future__ import annotations

import math
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
    oi_previous: float | None = None
    return_4h_pct: float | None = None
    return_24h_pct: float | None = None
    relative_volume: float | None = None
    bid_depth: float | None = None
    ask_depth: float | None = None
    depth_imbalance: float | None = None


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
        depth = self._get("/fapi/v1/depth", {"symbol": self.symbol, "limit": 20})
        oi = self._get("/fapi/v1/openInterest", {"symbol": self.symbol})
        funding = self._get("/fapi/v1/premiumIndex", {"symbol": self.symbol})
        klines = self._get(
            "/fapi/v1/klines",
            {"symbol": self.symbol, "interval": "1h", "limit": 26},
        )

        oi_hist = self._get(
            "/futures/data/openInterestHist",
            {"symbol": self.symbol, "period": "1h", "limit": 2},
        )
        current_oi = float(oi["openInterest"])
        previous_oi = None
        if isinstance(oi_hist, list):
            valid = [row for row in oi_hist if isinstance(row, dict) and row.get("sumOpenInterest") is not None]
            if len(valid) >= 2:
                valid.sort(key=lambda row: int(row.get("timestamp", 0)))
                previous_oi = float(valid[-2]["sumOpenInterest"])
            elif valid:
                previous_oi = float(valid[0]["sumOpenInterest"])
        oi_change = None
        if previous_oi is not None and previous_oi > 0:
            oi_change = (current_oi / previous_oi - 1.0) * 100.0

        bids = [(float(price), float(qty)) for price, qty in depth.get("bids", [])]
        asks = [(float(price), float(qty)) for price, qty in depth.get("asks", [])]
        bid_depth = sum(price * qty for price, qty in bids) if bids else None
        ask_depth = sum(price * qty for price, qty in asks) if asks else None
        total_depth = None if bid_depth is None or ask_depth is None else bid_depth + ask_depth
        depth_imbalance = None
        if total_depth and total_depth > 0:
            depth_imbalance = (bid_depth - ask_depth) / total_depth

        closed = klines[:-1] if len(klines) > 1 else klines
        closes = [float(row[4]) for row in closed]
        volumes = [float(row[5]) for row in closed]

        return_4h = None
        return_24h = None
        relative_volume = None
        if len(closes) >= 5 and closes[-5] != 0:
            return_4h = (closes[-1] / closes[-5] - 1.0) * 100.0
        if len(closes) >= 25 and closes[-25] != 0:
            return_24h = (closes[-1] / closes[-25] - 1.0) * 100.0
        if len(volumes) >= 25:
            baseline = sum(volumes[-25:-1]) / 24.0
            if baseline > 0:
                relative_volume = volumes[-1] / baseline

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
            oi_previous=previous_oi,
            return_4h_pct=return_4h,
            return_24h_pct=return_24h,
            relative_volume=relative_volume,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            depth_imbalance=depth_imbalance,
        )


def _bounded(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 2)


def _funding_rate_score(rate: float) -> tuple[float, str]:
    """Score funding as a contrarian crowding signal.

    Positive funding means longs pay shorts and is treated as bearish crowding;
    negative funding means shorts pay longs and is treated as bullish crowding.
    The piecewise scale is intentionally bounded and less sensitive to tiny
    rate changes than the previous linear formula.
    """
    magnitude = abs(rate)
    if magnitude <= 0.00005:
        score = 50.0
        regime = "NEUTRAL"
    elif magnitude <= 0.00020:
        score = 50.0 - (magnitude - 0.00005) / 0.00015 * 10.0
        regime = "LONG_CROWDED" if rate > 0 else "SHORT_CROWDED"
    elif magnitude <= 0.00050:
        score = 40.0 - (magnitude - 0.00020) / 0.00030 * 20.0
        regime = "LONG_CROWDED" if rate > 0 else "SHORT_CROWDED"
    else:
        score = max(0.0, 20.0 - (magnitude - 0.00050) / 0.00050 * 20.0)
        regime = "EXTREME_LONG" if rate > 0 else "EXTREME_SHORT"

    if rate < 0:
        score = 100.0 - score
    return _bounded(score), regime


def crypto_factor_adapters(adapter: BinanceMarketAdapter):
    # Fetch once so all five crypto factors use the same market snapshot.
    snap = adapter.snapshot()

    def trend(_: Any):
        from .intelligence_v2 import FactorResult
        if snap.return_4h_pct is None or snap.return_24h_pct is None:
            return FactorResult("trend", "UNAVAILABLE", provider="BINANCE_FUTURES")
        score = 50.0 + snap.return_4h_pct * 4.0 + snap.return_24h_pct * 2.0
        return FactorResult(
            "trend", "OK", _bounded(score), 0.9, "BINANCE_FUTURES",
            details={"symbol": snap.symbol, "return_4h_pct": round(snap.return_4h_pct, 4), "return_24h_pct": round(snap.return_24h_pct, 4)},
        )

    def volume(_: Any):
        from .intelligence_v2 import FactorResult
        if snap.relative_volume is None:
            return FactorResult("volume", "UNAVAILABLE", provider="BINANCE_FUTURES")
        direction = 1.0 if snap.return_4h_pct is not None and snap.return_4h_pct > 0 else -1.0 if snap.return_4h_pct is not None and snap.return_4h_pct < 0 else 0.0
        score = 50.0 + direction * min(20.0, max(0.0, snap.relative_volume - 1.0) * 25.0)
        return FactorResult(
            "volume", "OK", _bounded(score), 0.8, "BINANCE_FUTURES",
            details={"symbol": snap.symbol, "relative_volume_1h": round(snap.relative_volume, 4), "price_direction_4h": direction},
        )

    def liquidity(_: Any):
        from .intelligence_v2 import FactorResult
        mid = (snap.bid + snap.ask) / 2.0
        spread_bps = 0.0 if mid == 0 else (snap.ask - snap.bid) / mid * 10000.0
        spread_score = _bounded(100.0 - spread_bps * 10.0)
        if snap.bid_depth is None or snap.ask_depth is None or snap.depth_imbalance is None:
            return FactorResult("liquidity", "UNAVAILABLE", provider="BINANCE_FUTURES")
        total_depth_usd = snap.bid_depth + snap.ask_depth
        depth_score = _bounded((math.log10(max(total_depth_usd, 1.0)) - 5.0) * 20.0)
        balance_score = _bounded(100.0 - abs(snap.depth_imbalance) * 100.0)
        score = 0.5 * spread_score + 0.3 * depth_score + 0.2 * balance_score
        return FactorResult(
            "liquidity", "OK", _bounded(score), 0.9, "BINANCE_FUTURES",
            details={
                "symbol": snap.symbol,
                "spread_bps": round(spread_bps, 4),
                "bid_depth_usd": round(snap.bid_depth, 2),
                "ask_depth_usd": round(snap.ask_depth, 2),
                "total_depth_usd": round(total_depth_usd, 2),
                "depth_imbalance": round(snap.depth_imbalance, 4),
            },
        )

    def open_interest(_: Any):
        from .intelligence_v2 import FactorResult
        if snap.oi_change_pct is None:
            return FactorResult("open_interest", "UNAVAILABLE", provider="BINANCE_FUTURES")
        score = 50.0 + snap.oi_change_pct * 5.0
        return FactorResult(
            "open_interest", "OK", _bounded(score), 0.85, "BINANCE_FUTURES",
            details={
                "symbol": snap.symbol,
                "open_interest": snap.open_interest,
                "previous_open_interest": snap.oi_previous,
                "oi_change_pct_1h": round(snap.oi_change_pct, 4),
            },
        )

    def funding_rate(_: Any):
        from .intelligence_v2 import FactorResult
        score, regime = _funding_rate_score(snap.funding_rate)
        return FactorResult(
            "funding_rate",
            "OK",
            score,
            0.85,
            "BINANCE_FUTURES",
            details={
                "symbol": snap.symbol,
                "funding_rate": snap.funding_rate,
                "funding_rate_pct": round(snap.funding_rate * 100.0, 6),
                "funding_regime": regime,
            },
        )

    return trend, volume, liquidity, open_interest, funding_rate
