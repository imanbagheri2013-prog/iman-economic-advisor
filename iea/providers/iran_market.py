from __future__ import annotations

import os
import time
from datetime import datetime, time as dt_time, timezone
from typing import Any
from zoneinfo import ZoneInfo

import requests

from ..market_intelligence import MarketSnapshot

BASE_URL = "https://cdn.tsetmc.com/api"
TEHRAN = ZoneInfo("Asia/Tehran")
MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (1, 3)


class IranMarketProvider:
    """TSETMC market-data adapter with a historical-after-close fallback.

    The provider always returns the latest available trading session. During
    closed hours the snapshot is explicitly marked CLOSED and its data_date is
    the date of the completed session, so downstream analysis can still inspect
    the data without treating it as a live actionable quote.
    """

    def __init__(self, base_url: str | None = None, timeout: float = 15.0):
        self.base_url = (base_url or os.getenv("IEA_IRAN_MARKET_DATA_URL", BASE_URL)).rstrip("/")
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "Mozilla/5.0 IEA/1.0"})

    def _get(self, path: str) -> dict[str, Any]:
        response = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            try:
                response = self.session.get(f"{self.base_url}/{path.lstrip('/')}", timeout=self.timeout)
                if response.status_code not in {429, 500, 502, 503, 504} or attempt == MAX_ATTEMPTS:
                    break
            except requests.RequestException:
                if attempt == MAX_ATTEMPTS:
                    raise
            time.sleep(RETRY_DELAYS_SECONDS[attempt - 1])
        assert response is not None
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise ValueError("TSETMC response is not a JSON object")
        return payload

    def search(self, query: str) -> list[dict[str, Any]]:
        if not query or not query.strip():
            raise ValueError("Iran market symbol is required")
        payload = self._get(f"Instrument/GetInstrumentSearch/{query.strip()}")
        return payload.get("instrumentSearch") or []

    def resolve(self, symbol: str) -> dict[str, Any]:
        rows = self.search(symbol)
        if not rows:
            raise ValueError(f"Iran market symbol not found: {symbol}")
        exact = [row for row in rows if str(row.get("lVal18AFC", "")).strip() == symbol.strip()]
        return exact[0] if exact else rows[0]

    def snapshot(self, symbol: str) -> MarketSnapshot:
        instrument = self.resolve(symbol)
        ins_code = str(instrument.get("insCode") or "").strip()
        if not ins_code:
            raise ValueError(f"InsCode missing for {symbol}")

        info = self._get(f"ClosingPrice/GetClosingPriceInfo/{ins_code}").get("closingPriceInfo") or {}
        history = self._get(f"ClosingPrice/GetClosingPriceDailyList/{ins_code}/30").get("closingPriceDaily") or []
        latest = history[0] if history else info
        if not latest:
            raise ValueError(f"No closing data returned for {symbol}")

        data_date = _date_string(latest.get("dEven")) or _date_string(info.get("dEven"))
        observed_epoch = _epoch_from_tsetmc(data_date, latest.get("hEven") or info.get("hEven"))
        if observed_epoch is None:
            observed_at = datetime.now(timezone.utc)
        else:
            observed_at = datetime.fromtimestamp(observed_epoch, tz=timezone.utc)

        now_tehran = datetime.now(TEHRAN)
        market_status = "OPEN" if _is_open_window(now_tehran) and data_date == now_tehran.strftime("%Y%m%d") else "CLOSED"
        price = _number(latest.get("pClosing", latest.get("pDrCotVal", info.get("pClosing"))))
        previous = _number(latest.get("priceYesterday", info.get("priceYesterday")))
        if price is None:
            raise ValueError(f"closing price missing for {symbol}")

        return MarketSnapshot(
            symbol=str(instrument.get("lVal18AFC") or symbol).strip(),
            observed_at=observed_at,
            price=price,
            previous_close=previous,
            volume=_number(latest.get("qTotTran5J", info.get("qTotTran5J"))),
            high=_number(latest.get("priceMax", info.get("priceMax"))),
            low=_number(latest.get("priceMin", info.get("priceMin"))),
            source="tsetmc",
            market_status=market_status,
            data_date=data_date,
        )


def configured_iran_symbols() -> list[str]:
    raw = os.getenv("IEA_IR_SYMBOLS", "").strip()
    return [item.strip() for item in raw.split(",") if item.strip()]


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
        hour = raw // 10000
        minute = (raw // 100) % 100
        second = raw % 100
        date = datetime.strptime(data_date, "%Y%m%d").date()
        return datetime.combine(date, dt_time(hour, minute, second), tzinfo=TEHRAN).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _is_open_window(now: datetime) -> bool:
    # Tehran exchange session is normally 09:00-12:30 local time; the date
    # comparison above prevents an old session from being treated as live.
    return dt_time(9, 0) <= now.timetz().replace(tzinfo=None) <= dt_time(12, 30)
