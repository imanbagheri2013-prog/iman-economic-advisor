from __future__ import annotations

import os
import time
from datetime import datetime, time as dt_time, timezone
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

from ..market_intelligence import MarketSnapshot

BASE_URL = "https://cdn.tsetmc.com/api"
TEHRAN = ZoneInfo("Asia/Tehran")
MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (1, 3)


class IranMarketProvider:
    """TSETMC adapter for quote, history, real-money flow and shareholders."""

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
        payload = self._get(f"Instrument/GetInstrumentSearch/{quote(query.strip())}")
        return payload.get("instrumentSearch") or []

    def resolve(self, symbol: str) -> dict[str, Any]:
        rows = self.search(symbol)
        if not rows:
            raise ValueError(f"Iran market symbol not found: {symbol}")
        exact = [row for row in rows if str(row.get("lVal18AFC", "")).strip() == symbol.strip()]
        return exact[0] if exact else rows[0]

    def _ins_code(self, symbol: str) -> tuple[dict[str, Any], str]:
        instrument = self.resolve(symbol)
        ins_code = str(instrument.get("insCode") or "").strip()
        if not ins_code:
            raise ValueError(f"InsCode missing for {symbol}")
        return instrument, ins_code

    def snapshot(self, symbol: str) -> MarketSnapshot:
        instrument, ins_code = self._ins_code(symbol)
        info = self._get(f"ClosingPrice/GetClosingPriceInfo/{ins_code}").get("closingPriceInfo") or {}
        history = self._get(f"ClosingPrice/GetClosingPriceDailyList/{ins_code}/30").get("closingPriceDaily") or []
        latest = history[0] if history else info
        if not latest:
            raise ValueError(f"No closing data returned for {symbol}")
        data_date = _date_string(latest.get("dEven")) or _date_string(info.get("dEven"))
        observed_epoch = _epoch_from_tsetmc(data_date, latest.get("hEven") or info.get("hEven"))
        observed_at = datetime.fromtimestamp(observed_epoch, tz=timezone.utc) if observed_epoch else datetime.now(timezone.utc)
        now_tehran = datetime.now(TEHRAN)
        market_status = "OPEN" if _is_open_window(now_tehran) and data_date == now_tehran.strftime("%Y%m%d") else "CLOSED"
        price = _number(latest.get("pClosing", latest.get("pDrCotVal", info.get("pClosing"))))
        previous = _number(latest.get("priceYesterday", info.get("priceYesterday")))
        if price is None:
            raise ValueError(f"closing price missing for {symbol}")
        return MarketSnapshot(
            symbol=str(instrument.get("lVal18AFC") or symbol).strip(), observed_at=observed_at,
            price=price, previous_close=previous,
            volume=_number(latest.get("qTotTran5J", info.get("qTotTran5J"))),
            high=_number(latest.get("priceMax", info.get("priceMax"))), low=_number(latest.get("priceMin", info.get("priceMin"))),
            source="tsetmc", market_status=market_status, data_date=data_date,
        )

    def research_data(self, symbol: str, days: int = 23) -> dict[str, Any]:
        """Return raw-but-normalized data needed for a professional stock review."""
        instrument, ins_code = self._ins_code(symbol)
        info = self._get(f"Instrument/GetInstrumentInfo/{ins_code}").get("instrumentInfo") or {}
        daily = self._get(f"ClosingPrice/GetClosingPriceDailyList/{ins_code}/{max(30, days + 5)}").get("closingPriceDaily") or []
        client_history = self._get(f"ClientType/GetClientTypeHistory/{ins_code}").get("clientType") or []
        shareholders = self._get(f"Shareholder/GetInstrumentShareHolderLast/{ins_code}").get("shareHolder") or []
        client_history = [row for row in client_history if isinstance(row, dict)][:days]
        daily = [row for row in daily if isinstance(row, dict)][:days]
        current = daily[0] if daily else {}
        old = daily[-1] if daily else {}
        prices = [_number(row.get("pClosing", row.get("pDrCotVal"))) for row in daily]
        prices = [v for v in prices if v is not None]
        volumes = [_number(row.get("qTotTran5J")) for row in daily]
        volumes = [v for v in volumes if v is not None]
        first_price = prices[-1] if prices else None
        last_price = prices[0] if prices else None
        month_return = ((last_price / first_price) - 1) * 100 if first_price and last_price else None
        avg_volume = sum(volumes) / len(volumes) if volumes else None
        flow = _flow_summary(client_history)
        holder_change = _major_holder_change(shareholders)
        return {
            "symbol": str(instrument.get("lVal18AFC") or symbol).strip(),
            "instrument": instrument,
            "instrument_info": info,
            "data_date": _date_string(current.get("dEven")),
            "daily": daily,
            "client_type_history": client_history,
            "major_shareholders": shareholders,
            "one_month": {
                "observations": len(daily),
                "return_pct": month_return,
                "high": max(prices) if prices else None,
                "low": min(prices) if prices else None,
                "avg_volume": avg_volume,
                "latest_volume": _number(current.get("qTotTran5J")),
                "volume_trend_pct": ((volumes[0] / avg_volume) - 1) * 100 if volumes and avg_volume else None,
            },
            "money_flow": flow,
            "major_shareholder_change": holder_change,
        }


def configured_iran_symbols() -> list[str]:
    raw = os.getenv("IEA_IR_SYMBOLS", "").strip()
    return [item.strip() for item in raw.split(",") if item.strip()]


def _flow_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def total(key: str) -> float:
        return sum(_number(row.get(key)) or 0.0 for row in rows)
    buy_i, sell_i = total("buy_I_Volume"), total("sell_I_Volume")
    buy_n, sell_n = total("buy_N_Volume"), total("sell_N_Volume")
    buy_iv, sell_iv = total("buy_I_Value"), total("sell_I_Value")
    buy_nv, sell_nv = total("buy_N_Value"), total("sell_N_Value")
    return {
        "days": len(rows),
        "real_buy_volume": buy_i, "real_sell_volume": sell_i,
        "legal_buy_volume": buy_n, "legal_sell_volume": sell_n,
        "real_net_volume": buy_i - sell_i, "legal_net_volume": buy_n - sell_n,
        "real_net_value": buy_iv - sell_iv, "legal_net_value": buy_nv - sell_nv,
        "net_value": (buy_iv - sell_iv) + (buy_nv - sell_nv),
    }


def _major_holder_change(rows: list[dict[str, Any]]) -> dict[str, Any]:
    changes = []
    for row in rows:
        change = _number(row.get("change"))
        if change is not None:
            changes.append({"name": row.get("shareHolderName"), "change": change, "shares": _number(row.get("numberOfShares")), "percent": _number(row.get("perOfShares"))})
    changes.sort(key=lambda x: abs(x["change"] or 0), reverse=True)
    return {"available": bool(changes), "entries": changes[:20]}


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
        date = datetime.strptime(data_date, "%Y%m%d").date()
        return datetime.combine(date, dt_time(hour, minute, second), tzinfo=TEHRAN).timestamp()
    except (TypeError, ValueError, OverflowError):
        return None


def _is_open_window(now: datetime) -> bool:
    return dt_time(9, 0) <= now.timetz().replace(tzinfo=None) <= dt_time(12, 30)
