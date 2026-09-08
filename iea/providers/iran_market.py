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
    """TSETMC adapter for quote, history, flow, shareholders and Codal metadata."""

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

    def _get_optional(self, path: str) -> dict[str, Any]:
        try:
            return self._get(path)
        except (requests.RequestException, ValueError):
            return {}

    def search(self, query: str) -> list[dict[str, Any]]:
        if not query or not query.strip():
            raise ValueError("Iran market symbol is required")
        return self._get(f"Instrument/GetInstrumentSearch/{quote(query.strip())}").get("instrumentSearch") or []

    def resolve(self, symbol: str) -> dict[str, Any]:
        rows = self.search(symbol)
        if not rows:
            raise ValueError(f"Iran market symbol not found: {symbol}")
        exact = [row for row in rows if str(row.get("lVal18AFC", "")).strip() == symbol.strip()]
        return exact[0] if exact else rows[0]

    def _ins_code(self, symbol: str) -> tuple[dict[str, Any], str]:
        instrument = self.resolve(symbol)
        code = str(instrument.get("insCode") or "").strip()
        if not code:
            raise ValueError(f"InsCode missing for {symbol}")
        return instrument, code

    def _daily_return(self, symbol: str, days: int = 23) -> float | None:
        _, code = self._ins_code(symbol)
        rows = self._get(f"ClosingPrice/GetClosingPriceDailyList/{code}/{max(30, days + 5)}").get("closingPriceDaily") or []
        rows = [r for r in rows if isinstance(r, dict)][:days]
        prices = [_number(r.get("pClosing", r.get("pDrCotVal"))) for r in rows]
        prices = [p for p in prices if p is not None]
        if len(prices) < 2 or prices[-1] == 0:
            return None
        # TSETMC daily history is newest-first: return from oldest observation to newest.
        return round((prices[0] / prices[-1] - 1) * 100, 4)

    def snapshot(self, symbol: str) -> MarketSnapshot:
        instrument, code = self._ins_code(symbol)
        info = self._get(f"ClosingPrice/GetClosingPriceInfo/{code}").get("closingPriceInfo") or {}
        history = self._get(f"ClosingPrice/GetClosingPriceDailyList/{code}/30").get("closingPriceDaily") or []
        latest = history[0] if history else info
        if not latest:
            raise ValueError(f"No closing data returned for {symbol}")
        data_date = _date_string(latest.get("dEven")) or _date_string(info.get("dEven"))
        epoch = _epoch_from_tsetmc(data_date, latest.get("hEven") or info.get("hEven"))
        observed_at = datetime.fromtimestamp(epoch, tz=timezone.utc) if epoch else datetime.now(timezone.utc)
        now = datetime.now(TEHRAN)
        market_status = "OPEN" if _is_open_window(now) and data_date == now.strftime("%Y%m%d") else "CLOSED"
        price = _number(latest.get("pClosing", latest.get("pDrCotVal", info.get("pClosing"))))
        if price is None:
            raise ValueError(f"closing price missing for {symbol}")
        return MarketSnapshot(symbol=str(instrument.get("lVal18AFC") or symbol).strip(), observed_at=observed_at,
            price=price, previous_close=_number(latest.get("priceYesterday", info.get("priceYesterday"))),
            volume=_number(latest.get("qTotTran5J", info.get("qTotTran5J"))), high=_number(latest.get("priceMax", info.get("priceMax"))),
            low=_number(latest.get("priceMin", info.get("priceMin"))), source="tsetmc", market_status=market_status, data_date=data_date)

    def research_data(self, symbol: str, days: int = 23) -> dict[str, Any]:
        instrument, code = self._ins_code(symbol)
        info = self._get(f"Instrument/GetInstrumentInfo/{code}").get("instrumentInfo") or {}
        daily = self._get(f"ClosingPrice/GetClosingPriceDailyList/{code}/{max(30, days + 5)}").get("closingPriceDaily") or []
        client_history = self._get(f"ClientType/GetClientTypeHistory/{code}").get("clientType") or []
        shareholders = self._get(f"Shareholder/GetInstrumentShareHolderLast/{code}").get("shareHolder") or []
        codal = self._get(f"Codal/GetPreparedDataByInsCode/30/{code}").get("preparedData") or []
        statement_content_payload = self._get_optional(f"Codal/GetStatementContentByInsCode/{code}")
        statement_content = statement_content_payload.get("statementContent") or statement_content_payload.get("statementContents") or statement_content_payload.get("data") or []
        share_changes = self._get(f"Instrument/GetInstrumentShareChange/{code}").get("instrumentShareChange") or []
        daily = [r for r in daily if isinstance(r, dict)][:days]
        client_history = [r for r in client_history if isinstance(r, dict)][:days]
        prices = [_number(r.get("pClosing", r.get("pDrCotVal"))) for r in daily]
        prices = [v for v in prices if v is not None]
        volumes = [_number(r.get("qTotTran5J")) for r in daily]
        volumes = [v for v in volumes if v is not None]
        first_price, last_price = (prices[-1], prices[0]) if prices else (None, None)
        avg_volume = sum(volumes) / len(volumes) if volumes else None
        return {
            "symbol": str(instrument.get("lVal18AFC") or symbol).strip(), "instrument": instrument, "instrument_info": info,
            "data_date": _date_string(daily[0].get("dEven")) if daily else None, "daily": daily,
            "client_type_history": client_history, "major_shareholders": shareholders,
            "codal_filings": codal, "statement_content": statement_content, "share_changes": share_changes,
            "one_month": {"observations": len(daily), "return_pct": ((first_price / last_price) - 1) * 100 if first_price and last_price else None,
                "high": max(prices) if prices else None, "low": min(prices) if prices else None,
                "avg_volume": avg_volume, "latest_volume": volumes[0] if volumes else None,
                "volume_trend_pct": ((volumes[0] / avg_volume) - 1) * 100 if volumes and avg_volume else None},
            "money_flow": _flow_summary(client_history), "major_shareholder_change": _major_holder_change(shareholders),
        }


def configured_iran_symbols() -> list[str]:
    raw = os.getenv("IEA_IR_SYMBOLS", "").strip()
    return [x.strip() for x in raw.split(",") if x.strip()]


def _flow_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    def total(key: str) -> float:
        return sum(_number(r.get(key)) or 0.0 for r in rows)
    bi, si = total("buy_I_Volume"), total("sell_I_Volume")
    bn, sn = total("buy_N_Volume"), total("sell_N_Volume")
    biv, siv = total("buy_I_Value"), total("sell_I_Value")
    bnv, snv = total("buy_N_Value"), total("sell_N_Value")
    return {"days": len(rows), "real_buy_volume": bi, "real_sell_volume": si, "legal_buy_volume": bn, "legal_sell_volume": sn,
        "real_net_volume": bi-si, "legal_net_volume": bn-sn, "real_net_value": biv-siv, "legal_net_value": bnv-snv,
        "net_value": (biv-siv)+(bnv-snv)}


def _major_holder_change(rows: list[dict[str, Any]]) -> dict[str, Any]:
    changes = []
    for r in rows:
        change = _number(r.get("change"))
        if change is not None:
            changes.append({"name": r.get("shareHolderName"), "change": change, "shares": _number(r.get("numberOfShares")), "percent": _number(r.get("perOfShares"))})
    changes.sort(key=lambda x: abs(x["change"] or 0), reverse=True)
    return {"available": bool(changes), "entries": changes[:20]}


def _number(value: Any) -> float | None:
    try: return None if value is None else float(value)
    except (TypeError, ValueError): return None


def _date_string(value: Any) -> str | None:
    if value is None: return None
    text = str(value)
    return text if len(text) == 8 and text.isdigit() else None


def _epoch_from_tsetmc(data_date: str | None, h_even: Any) -> float | None:
    if not data_date: return None
    try:
        raw = int(h_even or 0); hour, minute, second = raw // 10000, (raw // 100) % 100, raw % 100
        date = datetime.strptime(data_date, "%Y%m%d").date()
        return datetime.combine(date, dt_time(hour, minute, second), tzinfo=TEHRAN).timestamp()
    except (TypeError, ValueError, OverflowError): return None


def _is_open_window(now: datetime) -> bool:
    return dt_time(9, 0) <= now.timetz().replace(tzinfo=None) <= dt_time(12, 30)
