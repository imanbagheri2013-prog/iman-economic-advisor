from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


TSETMC_CDN = "https://cdn.tsetmc.com/api"
TEDPIX_INSCODE = "32097828820363860"


@dataclass(frozen=True)
class IranMarketSnapshot:
    symbol: str
    price: float
    change_pct: float
    volume: float
    quote_volume: float
    bid: float
    ask: float
    return_1d_pct: float | None
    return_20d_pct: float | None
    relative_volume: float | None
    bid_depth: float | None
    ask_depth: float | None
    depth_imbalance: float | None
    breadth_up_pct: float | None
    breadth_down_pct: float | None
    total_symbols: int
    active_symbols: int


class IranMarketAdapter:
    """Read the Iran equity market as a whole from TSETMC public endpoints.

    This adapter deliberately does not fabricate open-interest or funding data:
    those crypto-derivatives factors are unavailable for the cash equity market
    and are handled as UNAVAILABLE by the Iran factor adapter.
    """

    provider = "TSETMC_CDN"

    def __init__(self, timeout: float = 15.0) -> None:
        self.timeout = timeout
        self.symbol = "IRAN_MARKET"

    def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        response = requests.get(
            f"{TSETMC_CDN}{path}",
            params=params,
            timeout=self.timeout,
            headers={"User-Agent": "Mozilla/5.0 IEA-Economic-Advisor"},
        )
        response.raise_for_status()
        payload = response.json()
        if isinstance(payload, dict):
            for key in ("marketwatch", "marketOverview", "closingPriceDaily"):
                if key in payload:
                    return payload[key]
        return payload

    @staticmethod
    def _number(row: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = row.get(key)
            if value is not None and value != "":
                try:
                    return float(value)
                except (TypeError, ValueError):
                    continue
        return None

    @classmethod
    def _index_closes(cls, payload: Any) -> list[float]:
        rows = payload if isinstance(payload, list) else []
        closes: list[float] = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            value = cls._number(row, "pClosing", "pc", "priceClosing", "closingPrice")
            if value is not None and value > 0:
                closes.append(value)
        return closes

    def snapshot(self) -> IranMarketSnapshot:
        overview = self._get("/MarketData/GetMarketOverview/1")
        if isinstance(overview, list):
            overview = overview[0] if overview else {}
        if not isinstance(overview, dict):
            overview = {}

        watch = self._get(
            "/ClosingPrice/GetMarketWatch",
            {
                "market": 0,
                "industrialGroup": "",
                "paperTypes[0]": 1,
                "paperTypes[1]": 2,
                "paperTypes[2]": 3,
                "paperTypes[3]": 4,
                "paperTypes[4]": 5,
                "paperTypes[5]": 6,
                "paperTypes[6]": 7,
                "paperTypes[7]": 8,
                "paperTypes[8]": 9,
                "showTraded": True,
                "withBestLimits": True,
                "hEven": 0,
                "RefID": 0,
            },
        )
        rows = [row for row in watch if isinstance(row, dict)] if isinstance(watch, list) else []

        active = []
        total_volume = 0.0
        total_value = 0.0
        total_bid = 0.0
        total_ask = 0.0
        up = down = 0
        for row in rows:
            last = self._number(row, "pl", "pDrCotVal")
            prev = self._number(row, "py", "priceYesterday")
            volume = self._number(row, "qTotTran5J", "volume") or 0.0
            value = self._number(row, "qTotCap", "value") or 0.0
            if last is None or prev is None or prev <= 0:
                continue
            active.append(row)
            total_volume += volume
            total_value += value
            if last > prev:
                up += 1
            elif last < prev:
                down += 1
            bid_qty = self._number(row, "qTitMeDem", "bidQty")
            ask_qty = self._number(row, "qTitMeOf", "askQty")
            if bid_qty is not None and last > 0:
                total_bid += bid_qty * last
            if ask_qty is not None and last > 0:
                total_ask += ask_qty * last

        if not active:
            raise ValueError("TSETMC market watch returned no active instruments")

        index_history = self._get(f"/ClosingPrice/GetClosingPriceDailyList/{TEDPIX_INSCODE}/0")
        closes = self._index_closes(index_history)
        return_1d = (closes[0] / closes[1] - 1.0) * 100.0 if len(closes) >= 2 and closes[1] else None
        return_20d = (closes[0] / closes[20] - 1.0) * 100.0 if len(closes) >= 21 and closes[20] else None

        index_value = self._number(overview, "indexLastValue", "indexValue")
        index_change = self._number(overview, "indexChange", "indexChangeValue")
        if index_value is None:
            index_value = closes[0] if closes else 0.0
        if index_change is None:
            index_change = return_1d or 0.0

        total_depth = total_bid + total_ask
        imbalance = (total_bid - total_ask) / total_depth if total_depth else None
        active_count = len(active)
        breadth_up = up / active_count * 100.0 if active_count else None
        breadth_down = down / active_count * 100.0 if active_count else None

        return IranMarketSnapshot(
            symbol=self.symbol,
            price=index_value,
            change_pct=index_change,
            volume=total_volume,
            quote_volume=total_value,
            bid=index_value,
            ask=index_value,
            return_1d_pct=return_1d,
            return_20d_pct=return_20d,
            relative_volume=None,
            bid_depth=total_bid or None,
            ask_depth=total_ask or None,
            depth_imbalance=imbalance,
            breadth_up_pct=breadth_up,
            breadth_down_pct=breadth_down,
            total_symbols=len(rows),
            active_symbols=active_count,
        )


def iran_factor_adapters(adapter: IranMarketAdapter):
    """Return factor functions for the Iran cash-equity market."""
    from .intelligence_v2 import FactorResult

    cache: dict[str, Any] = {"loaded": False, "snapshot": None, "error": None}

    def get_snapshot() -> IranMarketSnapshot | None:
        if not cache["loaded"]:
            try:
                cache["snapshot"] = adapter.snapshot()
            except (requests.RequestException, OSError, ValueError, KeyError, TypeError) as exc:
                cache["error"] = exc
            cache["loaded"] = True
        if cache["error"] is not None:
            return None
        return cache["snapshot"]

    def unavailable(name: str):
        error = cache["error"]
        details = {"provider": adapter.provider, "reason": "market_data_unavailable"}
        if error is not None:
            details.update({"error_type": type(error).__name__, "error": str(error)})
        return FactorResult(name, "UNAVAILABLE", provider=adapter.provider, details=details)

    def trend(_: Any):
        snap = get_snapshot()
        if snap is None:
            return unavailable("trend")
        if snap.return_1d_pct is None or snap.return_20d_pct is None:
            return FactorResult("trend", "UNAVAILABLE", provider=adapter.provider)
        score = max(0.0, min(100.0, 50.0 + snap.return_1d_pct * 3.0 + snap.return_20d_pct * 1.5))
        return FactorResult(
            "trend", "OK", round(score, 2), 0.9, adapter.provider,
            details={"symbol": snap.symbol, "return_1d_pct": round(snap.return_1d_pct, 4), "return_20d_pct": round(snap.return_20d_pct, 4), "sample_count": 21},
        )

    def volume(_: Any):
        snap = get_snapshot()
        if snap is None:
            return unavailable("volume")
        if snap.volume <= 0 or snap.active_symbols <= 0:
            return FactorResult("volume", "UNAVAILABLE", provider=adapter.provider)
        score = min(100.0, 50.0 + (snap.breadth_up_pct or 0.0) * 0.25 - (snap.breadth_down_pct or 0.0) * 0.15)
        return FactorResult(
            "volume", "OK", round(score, 2), 0.75, adapter.provider,
            details={"symbol": snap.symbol, "market_volume": snap.volume, "market_value": snap.quote_volume, "breadth_up_pct": snap.breadth_up_pct, "breadth_down_pct": snap.breadth_down_pct, "sample_count": snap.active_symbols},
        )

    def liquidity(_: Any):
        snap = get_snapshot()
        if snap is None:
            return unavailable("liquidity")
        if snap.bid_depth is None or snap.ask_depth is None or snap.depth_imbalance is None:
            return FactorResult("liquidity", "UNAVAILABLE", provider=adapter.provider)
        balance_score = max(0.0, min(100.0, 100.0 - abs(snap.depth_imbalance) * 100.0))
        return FactorResult(
            "liquidity", "OK", round(balance_score, 2), 0.75, adapter.provider,
            details={"symbol": snap.symbol, "bid_depth_usd": snap.bid_depth, "ask_depth_usd": snap.ask_depth, "depth_imbalance": snap.depth_imbalance, "sample_count": snap.active_symbols},
        )

    def unavailable_derivatives(name: str):
        return FactorResult(name, "UNAVAILABLE", provider=adapter.provider, details={"reason": "not_applicable_to_iran_cash_equities"})

    return trend, volume, liquidity, unavailable_derivatives, unavailable_derivatives
