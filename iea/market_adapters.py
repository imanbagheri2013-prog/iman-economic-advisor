from __future__ import annotations

import math
import os
from dataclasses import dataclass
from typing import Any

import requests


BINANCE_FAPI = "https://fapi.binance.com"
BYBIT_API = "https://api.bybit.com"
OKX_API = "https://www.okx.com"


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

    provider = "BINANCE_FUTURES"

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
        klines = self._get("/fapi/v1/klines", {"symbol": self.symbol, "interval": "1h", "limit": 26})
        oi_hist = self._get("/futures/data/openInterestHist", {"symbol": self.symbol, "period": "1h", "limit": 2})

        current_oi = float(oi["openInterest"])
        previous_oi = None
        if isinstance(oi_hist, list):
            valid = [row for row in oi_hist if isinstance(row, dict) and row.get("sumOpenInterest") is not None]
            if len(valid) >= 2:
                valid.sort(key=lambda row: int(row.get("timestamp", 0)))
                previous_oi = float(valid[-2]["sumOpenInterest"])
            elif valid:
                previous_oi = float(valid[0]["sumOpenInterest"])
        oi_change = None if previous_oi is None or previous_oi <= 0 else (current_oi / previous_oi - 1.0) * 100.0

        bids = [(float(price), float(qty)) for price, qty in depth.get("bids", [])]
        asks = [(float(price), float(qty)) for price, qty in depth.get("asks", [])]
        bid_depth = sum(price * qty for price, qty in bids) if bids else None
        ask_depth = sum(price * qty for price, qty in asks) if asks else None
        total_depth = None if bid_depth is None or ask_depth is None else bid_depth + ask_depth
        depth_imbalance = None if not total_depth else (bid_depth - ask_depth) / total_depth

        closed = klines[:-1] if len(klines) > 1 else klines
        closes = [float(row[4]) for row in closed]
        volumes = [float(row[5]) for row in closed]
        return_4h = (closes[-1] / closes[-5] - 1.0) * 100.0 if len(closes) >= 5 and closes[-5] else None
        return_24h = (closes[-1] / closes[-25] - 1.0) * 100.0 if len(closes) >= 25 and closes[-25] else None
        relative_volume = None
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


class BybitMarketAdapter:
    """Read public Bybit linear perpetual market data as a Binance fallback."""

    provider = "BYBIT_LINEAR"

    def __init__(self, symbol: str | None = None, timeout: float = 10.0) -> None:
        self.symbol = (symbol or os.getenv("IEA_MARKET_SYMBOL", "BTCUSDT")).upper()
        self.timeout = timeout

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(f"{BYBIT_API}{path}", params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("retCode") != 0:
            raise ValueError(f"Bybit API error: {payload.get('retCode') if isinstance(payload, dict) else 'invalid_payload'}")
        return payload

    def snapshot(self) -> MarketSnapshot:
        params = {"category": "linear", "symbol": self.symbol}
        ticker = self._get("/v5/market/tickers", params)["result"]["list"][0]
        book = self._get("/v5/market/orderbook", {**params, "limit": 20})["result"]
        klines = self._get("/v5/market/kline", {**params, "interval": "60", "limit": 26})["result"]["list"]
        oi_hist = self._get("/v5/market/open-interest", {**params, "intervalTime": "1h", "limit": 2})["result"]["list"]

        current_oi = float(ticker["openInterest"])
        previous_oi = None
        if isinstance(oi_hist, list):
            valid = [row for row in oi_hist if row.get("openInterest") is not None]
            if len(valid) >= 2:
                valid.sort(key=lambda row: int(row["timestamp"]))
                previous_oi = float(valid[-2]["openInterest"])
            elif valid:
                previous_oi = float(valid[0]["openInterest"])
        oi_change = None if previous_oi is None or previous_oi <= 0 else (current_oi / previous_oi - 1.0) * 100.0

        bids = [(float(row[0]), float(row[1])) for row in book.get("b", [])]
        asks = [(float(row[0]), float(row[1])) for row in book.get("a", [])]
        bid_depth = sum(price * qty for price, qty in bids) if bids else None
        ask_depth = sum(price * qty for price, qty in asks) if asks else None
        total_depth = None if bid_depth is None or ask_depth is None else bid_depth + ask_depth
        depth_imbalance = None if not total_depth else (bid_depth - ask_depth) / total_depth

        klines = list(reversed(klines))
        closed = klines[:-1] if len(klines) > 1 else klines
        closes = [float(row[4]) for row in closed]
        volumes = [float(row[5]) for row in closed]
        return_4h = (closes[-1] / closes[-5] - 1.0) * 100.0 if len(closes) >= 5 and closes[-5] else None
        return_24h = (closes[-1] / closes[-25] - 1.0) * 100.0 if len(closes) >= 25 and closes[-25] else None
        relative_volume = None
        if len(volumes) >= 25:
            baseline = sum(volumes[-25:-1]) / 24.0
            if baseline > 0:
                relative_volume = volumes[-1] / baseline

        return MarketSnapshot(
            symbol=self.symbol,
            price=float(ticker["lastPrice"]),
            change_pct=float(ticker["price24hPcnt"]) * 100.0,
            volume=float(ticker["volume24h"]),
            quote_volume=float(ticker["turnover24h"]),
            bid=float(ticker.get("bid1Price", book["b"][0][0])),
            ask=float(ticker.get("ask1Price", book["a"][0][0])),
            open_interest=current_oi,
            funding_rate=float(ticker["fundingRate"]),
            oi_change_pct=oi_change,
            oi_previous=previous_oi,
            return_4h_pct=return_4h,
            return_24h_pct=return_24h,
            relative_volume=relative_volume,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            depth_imbalance=depth_imbalance,
        )


class OKXMarketAdapter:
    """Read public OKX BTC-USDT perpetual market data as a second fallback."""

    provider = "OKX_SWAP"

    def __init__(self, symbol: str | None = None, timeout: float = 10.0) -> None:
        self.symbol = (symbol or os.getenv("IEA_MARKET_SYMBOL", "BTCUSDT")).upper()
        self.timeout = timeout
        self.inst_id = self._instrument_id(self.symbol)

    @staticmethod
    def _instrument_id(symbol: str) -> str:
        if symbol.endswith("USDT"):
            return f"{symbol[:-4]}-USDT-SWAP"
        if symbol.endswith("USD"):
            return f"{symbol[:-3]}-USD-SWAP"
        raise ValueError(f"Unsupported OKX symbol: {symbol}")

    def _get(self, path: str, params: dict[str, Any]) -> dict[str, Any]:
        response = requests.get(f"{OKX_API}{path}", params=params, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("code") != "0":
            raise ValueError(f"OKX API error: {payload.get('code') if isinstance(payload, dict) else 'invalid_payload'}")
        return payload

    def snapshot(self) -> MarketSnapshot:
        ticker = self._get("/api/v5/market/ticker", {"instId": self.inst_id})["data"][0]
        book = self._get("/api/v5/market/books", {"instId": self.inst_id, "sz": "20"})["data"][0]
        funding = self._get("/api/v5/public/funding-rate", {"instId": self.inst_id})["data"][0]
        oi = self._get("/api/v5/public/open-interest", {"instType": "SWAP", "instId": self.inst_id})["data"][0]
        candles = self._get("/api/v5/market/candles", {"instId": self.inst_id, "bar": "1H", "limit": "26"})["data"]

        # OKX returns candles newest-first; exclude the current unfinished candle.
        candles = list(reversed(candles))
        closed = candles[:-1] if len(candles) > 1 else candles
        closes = [float(row[4]) for row in closed]
        volumes = [float(row[5]) for row in closed]
        return_4h = (closes[-1] / closes[-5] - 1.0) * 100.0 if len(closes) >= 5 and closes[-5] else None
        return_24h = (closes[-1] / closes[-25] - 1.0) * 100.0 if len(closes) >= 25 and closes[-25] else None
        relative_volume = None
        if len(volumes) >= 25:
            baseline = sum(volumes[-25:-1]) / 24.0
            if baseline > 0:
                relative_volume = volumes[-1] / baseline

        bids = [(float(row[0]), float(row[1])) for row in book.get("bids", [])]
        asks = [(float(row[0]), float(row[1])) for row in book.get("asks", [])]
        bid_depth = sum(price * qty for price, qty in bids) if bids else None
        ask_depth = sum(price * qty for price, qty in asks) if asks else None
        total_depth = None if bid_depth is None or ask_depth is None else bid_depth + ask_depth
        depth_imbalance = None if not total_depth else (bid_depth - ask_depth) / total_depth

        current_oi = float(oi["oi"])
        return MarketSnapshot(
            symbol=self.symbol,
            price=float(ticker["last"]),
            change_pct=((float(ticker["last"]) / float(ticker["open24h"])) - 1.0) * 100.0 if float(ticker["open24h"]) else 0.0,
            volume=float(ticker["vol24h"]),
            quote_volume=float(ticker["volCcy24h"]),
            bid=float(ticker["bidPx"]),
            ask=float(ticker["askPx"]),
            open_interest=current_oi,
            funding_rate=float(funding["fundingRate"]),
            oi_change_pct=None,
            oi_previous=None,
            return_4h_pct=return_4h,
            return_24h_pct=return_24h,
            relative_volume=relative_volume,
            bid_depth=bid_depth,
            ask_depth=ask_depth,
            depth_imbalance=depth_imbalance,
        )


class ResilientMarketAdapter:
    """Try the primary provider, then Bybit, then OKX."""

    def __init__(self, primary: Any | None = None, secondary: Any | None = None, tertiary: Any | None = None) -> None:
        self.primary = primary or BinanceMarketAdapter()
        self.secondary = secondary or BybitMarketAdapter(symbol=self.primary.symbol, timeout=self.primary.timeout)
        self.tertiary = tertiary or OKXMarketAdapter(symbol=self.primary.symbol, timeout=self.primary.timeout)
        self.symbol = self.primary.symbol
        self.provider = self.primary.provider

    def snapshot(self) -> MarketSnapshot:
        try:
            snapshot = self.primary.snapshot()
            self.provider = self.primary.provider
            return snapshot
        except (requests.RequestException, OSError, ValueError, KeyError, TypeError):
            try:
                snapshot = self.secondary.snapshot()
                self.provider = self.secondary.provider
                return snapshot
            except (requests.RequestException, OSError, ValueError, KeyError, TypeError):
                snapshot = self.tertiary.snapshot()
                self.provider = self.tertiary.provider
                return snapshot


def _bounded(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return round(max(low, min(high, value)), 2)


def _funding_rate_score(rate: float) -> tuple[float, str]:
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


def crypto_factor_adapters(adapter: Any):
    snapshot_cache: dict[str, Any] = {"loaded": False, "snapshot": None, "error": None}

    def get_snapshot() -> tuple[MarketSnapshot | None, Exception | None]:
        if not snapshot_cache["loaded"]:
            try:
                snapshot_cache["snapshot"] = adapter.snapshot()
            except (requests.RequestException, OSError, ValueError, KeyError, TypeError) as exc:
                snapshot_cache["error"] = exc
            snapshot_cache["loaded"] = True
        return snapshot_cache["snapshot"], snapshot_cache["error"]

    def unavailable(name: str, error: Exception):
        from .intelligence_v2 import FactorResult
        status_code = getattr(getattr(error, "response", None), "status_code", None)
        provider = getattr(adapter, "provider", "BINANCE_FUTURES")
        details = {"provider": provider, "error_type": type(error).__name__, "error": str(error)}
        if status_code is not None:
            details["status_code"] = status_code
        return FactorResult(name, "UNAVAILABLE", provider=provider, details=details)

    def snapshot_or_unavailable(name: str):
        snap, error = get_snapshot()
        if error is not None:
            return None, unavailable(name, error)
        return snap, None

    def trend(_: Any):
        from .intelligence_v2 import FactorResult
        snap, failure = snapshot_or_unavailable("trend")
        if failure is not None:
            return failure
        if snap.return_4h_pct is None or snap.return_24h_pct is None:
            return FactorResult("trend", "UNAVAILABLE", provider=getattr(adapter, "provider", "UNKNOWN"))
        score = 50.0 + snap.return_4h_pct * 4.0 + snap.return_24h_pct * 2.0
        return FactorResult("trend", "OK", _bounded(score), 0.9, getattr(adapter, "provider", "UNKNOWN"), details={"symbol": snap.symbol, "return_4h_pct": round(snap.return_4h_pct, 4), "return_24h_pct": round(snap.return_24h_pct, 4)})

    def volume(_: Any):
        from .intelligence_v2 import FactorResult
        snap, failure = snapshot_or_unavailable("volume")
        if failure is not None:
            return failure
        if snap.relative_volume is None:
            return FactorResult("volume", "UNAVAILABLE", provider=getattr(adapter, "provider", "UNKNOWN"))
        direction = 1.0 if snap.return_4h_pct is not None and snap.return_4h_pct > 0 else -1.0 if snap.return_4h_pct is not None and snap.return_4h_pct < 0 else 0.0
        score = 50.0 + direction * min(20.0, max(0.0, snap.relative_volume - 1.0) * 25.0)
        return FactorResult("volume", "OK", _bounded(score), 0.8, getattr(adapter, "provider", "UNKNOWN"), details={"symbol": snap.symbol, "relative_volume_1h": round(snap.relative_volume, 4), "price_direction_4h": direction})

    def liquidity(_: Any):
        from .intelligence_v2 import FactorResult
        snap, failure = snapshot_or_unavailable("liquidity")
        if failure is not None:
            return failure
        mid = (snap.bid + snap.ask) / 2.0
        spread_bps = 0.0 if mid == 0 else (snap.ask - snap.bid) / mid * 10000.0
        spread_score = _bounded(100.0 - spread_bps * 10.0)
        if snap.bid_depth is None or snap.ask_depth is None or snap.depth_imbalance is None:
            return FactorResult("liquidity", "UNAVAILABLE", provider=getattr(adapter, "provider", "UNKNOWN"))
        total_depth_usd = snap.bid_depth + snap.ask_depth
        depth_score = _bounded((math.log10(max(total_depth_usd, 1.0)) - 5.0) * 20.0)
        balance_score = _bounded(100.0 - abs(snap.depth_imbalance) * 100.0)
        score = 0.5 * spread_score + 0.3 * depth_score + 0.2 * balance_score
        return FactorResult("liquidity", "OK", _bounded(score), 0.9, getattr(adapter, "provider", "UNKNOWN"), details={"symbol": snap.symbol, "spread_bps": round(spread_bps, 4), "bid_depth_usd": round(snap.bid_depth, 2), "ask_depth_usd": round(snap.ask_depth, 2), "total_depth_usd": round(total_depth_usd, 2), "depth_imbalance": round(snap.depth_imbalance, 4)})

    def open_interest(_: Any):
        from .intelligence_v2 import FactorResult
        snap, failure = snapshot_or_unavailable("open_interest")
        if failure is not None:
            return failure
        if snap.oi_change_pct is None:
            return FactorResult("open_interest", "UNAVAILABLE", provider=getattr(adapter, "provider", "UNKNOWN"), details={"reason": "historical_open_interest_unavailable"})
        score = 50.0 + snap.oi_change_pct * 5.0
        return FactorResult("open_interest", "OK", _bounded(score), 0.85, getattr(adapter, "provider", "UNKNOWN"), details={"symbol": snap.symbol, "open_interest": snap.open_interest, "previous_open_interest": snap.oi_previous, "oi_change_pct_1h": round(snap.oi_change_pct, 4)})

    def funding_rate(_: Any):
        from .intelligence_v2 import FactorResult
        snap, failure = snapshot_or_unavailable("funding_rate")
        if failure is not None:
            return failure
        score, regime = _funding_rate_score(snap.funding_rate)
        return FactorResult("funding_rate", "OK", score, 0.85, getattr(adapter, "provider", "UNKNOWN"), details={"symbol": snap.symbol, "funding_rate": snap.funding_rate, "funding_rate_pct": round(snap.funding_rate * 100.0, 6), "funding_regime": regime})

    return trend, volume, liquidity, open_interest, funding_rate
