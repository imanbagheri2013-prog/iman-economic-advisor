from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

import requests

from ..market_intelligence import MarketSnapshot

DEFAULT_MIRROR_URL = "https://raw.githubusercontent.com/imanbagheri2013-prog/iman-economic-advisor/market-data/data/iran_market_live.json"
LEGACY_MARKETWATCH_URL = "http://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx"


class IranMarketMirrorProvider:
    """Read the latest TSETMC snapshot collected by GitHub Actions."""

    def __init__(self, url: str | None = None, timeout: float = 12.0) -> None:
        self.url = (url or os.getenv("IEA_IRAN_MARKET_MIRROR_URL", DEFAULT_MIRROR_URL)).strip()
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "IEA-Economic-Advisor/market-mirror", "Accept": "application/json"})

    def _payload(self) -> dict[str, Any]:
        response = self.session.get(self.url, timeout=self.timeout)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), dict):
            raise ValueError("Iran market mirror payload is invalid")
        return payload

    def snapshot(self, symbol: str) -> MarketSnapshot:
        payload = self._payload()
        row = payload["symbols"].get(symbol)
        if not isinstance(row, dict):
            raise ValueError(f"Iran market mirror has no data for {symbol}")
        instrument = row.get("instrument") or {}
        info = row.get("instrument_info") or {}
        daily = [x for x in row.get("daily", []) if isinstance(x, dict)]
        latest = daily[0] if daily else info
        if not latest:
            raise ValueError(f"Iran market mirror has no quote for {symbol}")
        data_date = _date_string(latest.get("dEven")) or _date_string(info.get("dEven"))
        epoch = _epoch_from_tsetmc(data_date, latest.get("hEven") or info.get("hEven"))
        observed_at = datetime.fromtimestamp(epoch, tz=timezone.utc) if epoch else datetime.now(timezone.utc)
        price = _number(latest.get("pClosing", latest.get("pDrCotVal", info.get("pClosing"))))
        if price is None:
            raise ValueError(f"closing price missing for {symbol}")
        previous = _number(latest.get("priceYesterday", info.get("priceYesterday")))
        volume = _number(latest.get("qTotTran5J", info.get("qTotTran5J")))
        return MarketSnapshot(
            symbol=str(instrument.get("lVal18AFC") or symbol).strip(), observed_at=observed_at,
            price=price, previous_close=previous, volume=volume,
            high=_number(latest.get("priceMax", info.get("priceMax"))),
            low=_number(latest.get("priceMin", info.get("priceMin"))),
            source="tsetmc-github-actions", market_status="CLOSED", data_date=data_date,
        )


class LegacyTsetmcMarketProvider:
    """Use the legacy MarketWatchPlus feed as a Railway-compatible fallback."""

    def __init__(self, url: str = LEGACY_MARKETWATCH_URL, timeout: float = 15.0) -> None:
        self.url = url
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0", "Accept": "text/plain,text/*,*/*"})

    def snapshot(self, symbol: str) -> MarketSnapshot:
        response = self.session.get(self.url, timeout=self.timeout)
        response.raise_for_status()
        text = response.content.decode("utf-8", errors="ignore")
        parts = text.split("@")
        if len(parts) < 3:
            raise ValueError("legacy MarketWatchPlus response has no price section")
        for raw in parts[2].split(";"):
            fields = raw.split(",")
            if len(fields) < 23:
                continue
            if fields[2].strip() != symbol:
                continue
            observed_at = datetime.now(timezone.utc)
            data_date = observed_at.astimezone().strftime("%Y%m%d")
            price = _number(fields[6])
            previous = _number(fields[13])
            if price is None:
                raise ValueError(f"legacy closing price missing for {symbol}")
            return MarketSnapshot(
                symbol=symbol, observed_at=observed_at, price=price,
                previous_close=previous, volume=_number(fields[9]),
                high=_number(fields[12]), low=_number(fields[11]),
                source="tsetmc-legacy-marketwatch", market_status="CLOSED", data_date=data_date,
            )
        raise ValueError(f"legacy MarketWatchPlus has no row for {symbol}")


def _number(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _date_string(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value)
    return text if len(text) == 8 and text.isdigit() else None


def _epoch_from_tsetmc(data_date: str | None, h_even: Any) -> float | None:
    if not data_date:
        return None
    try:
        raw = int(h_even or 0)
        hour, minute, second = raw // 10000, (raw // 100) % 100, raw % 100
        from zoneinfo import ZoneInfo
        from datetime import time
        tehran = ZoneInfo("Asia/Tehran")
        parsed = datetime.strptime(data_date, "%Y%m%d").date()
        return datetime.combine(parsed, time(hour, minute, second), tzinfo=tehran).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


class FallbackIranMarketProvider:
    """Prefer the GitHub mirror, then legacy MarketWatch, then direct CDN TSETMC."""

    def __init__(self) -> None:
        from .iran_market import IranMarketProvider
        self.mirror = IranMarketMirrorProvider()
        self.legacy = LegacyTsetmcMarketProvider()
        self.direct = IranMarketProvider()

    def snapshot(self, symbol: str) -> MarketSnapshot:
        failures: list[str] = []
        for name, provider in (("mirror", self.mirror), ("legacy", self.legacy), ("direct", self.direct)):
            try:
                return provider.snapshot(symbol)
            except Exception as exc:
                failures.append(f"{name}={type(exc).__name__}: {exc}")
        raise RuntimeError("Iran market unavailable; " + " | ".join(failures))
