from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

OUT = Path("data/iran_market_live.json")
WEBGW_BASE = "https://webgw.tse.ir/InstrumentProvider/api/v1/MarketWatch"
WEBGW_ENDPOINTS = {
    "cash": f"{WEBGW_BASE}/MarketWatchCash/fa",
    "etf": f"{WEBGW_BASE}/MarketWatchEtf/fa",
    "future": f"{WEBGW_BASE}/MarketWatchFuture/fa",
    "option": f"{WEBGW_BASE}/MarketWatchOption/fa",
    "debt": f"{WEBGW_BASE}/MarketWatchDebt/fa",
}
CDN_URL = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&industrialGroup=&paperTypes%5B0%5D=1&paperTypes%5B1%5D=2&paperTypes%5B2%5D=3&paperTypes%5B3%5D=4&paperTypes%5B4%5D=5&paperTypes%5B5%5D=6&paperTypes%5B6%5D=7&paperTypes%5B7%5D=8&paperTypes%5B8%5D=9&showTraded=false&withBestLimits=false&hEven=0&RefID=0"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.tse.ir/",
}


def value(v):
    if isinstance(v, dict):
        return v.get("value")
    return v


def first(row, *names):
    for name in names:
        if name in row and row[name] not in (None, "", "-"):
            return value(row[name])
    return None


def number(v):
    if v in (None, "", "-"):
        return None
    try:
        return float(str(v).replace(",", "").replace("٬", "").replace("٫", "."))
    except (TypeError, ValueError):
        return None


def build_item(row):
    symbol = str(first(row, "instrumentName", "instrument_Name", "symbol") or "").strip()
    isin = str(first(row, "instrumentId", "instrumentid") or "").strip()
    if not symbol or not isin:
        return None
    closing = number(first(row, "closingPrice"))
    last = number(first(row, "lastPrice"))
    previous = number(first(row, "yesterdayPrice"))
    volume = number(first(row, "tradeVolume"))
    if closing is None and last is None:
        return None
    return {
        "instrument": {
            "lVal18AFC": symbol,
            "insCode": None,
            "isin": isin,
        },
        "instrument_info": {
            "pClosing": closing if closing is not None else last,
            "pDrCotVal": last if last is not None else closing,
            "priceYesterday": previous,
            "priceMax": number(first(row, "maxValue")),
            "priceMin": number(first(row, "minValue")),
            "qTotTran5J": volume,
            "hEven": "",
            "quoteStatus": "ACTIVE" if volume not in (None, 0) else "SUSPENDED_OR_NO_TRADE",
        },
        "market": {
            "marketId": first(row, "marketid"),
            "marketName": first(row, "marketname"),
            "marketType": first(row, "markettypeid", "markettypename"),
            "industry": first(row, "industryid", "industryname"),
            "state": first(row, "stateid", "statename"),
        },
        "daily": [],
        "client_type_history": [],
        "major_shareholders": [],
        "codal_filings": [],
        "statement_content": [],
        "share_changes": [],
    }


def fetch_webgw(session):
    symbols = {}
    counts = {}
    errors = []
    for kind, url in WEBGW_ENDPOINTS.items():
        try:
            r = session.get(url, timeout=(6, 20))
            r.raise_for_status()
            payload = r.json()
            rows = payload.get("Items", []) if isinstance(payload, dict) else []
            if not isinstance(rows, list):
                raise RuntimeError("Items is not a list")
            valid = 0
            for row in rows:
                if not isinstance(row, dict):
                    continue
                item = build_item(row)
                if item:
                    symbols[item["instrument"]["isin"]] = item
                    valid += 1
            counts[kind] = valid
        except Exception as exc:
            errors.append(f"{kind}: {type(exc).__name__}: {exc}")
    if len(symbols) >= 1000:
        return symbols, f"tse-webgw-marketwatch:{counts}", errors
    raise RuntimeError(f"webgw returned only {len(symbols)} valid symbols; counts={counts}; errors={errors}")


def fetch_cdn(session):
    r = session.get(CDN_URL, timeout=(6, 20))
    r.raise_for_status()
    payload = r.json()
    rows = payload.get("marketwatch", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("CDN marketwatch is empty")
    symbols = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(first(row, "lVal18AFC", "lVal18AfC", "symbol", "instrumentName") or "").strip()
        if not symbol:
            continue
        closing = number(first(row, "pClosing", "closingPrice"))
        last = number(first(row, "pDrCotVal", "lastPrice"))
        previous = number(first(row, "priceYesterday", "py"))
        if closing is None and last is None:
            continue
        item = {
            "instrument": {"lVal18AFC": symbol, "insCode": first(row, "insCode", "inscode"), "isin": first(row, "isin", "ISIN")},
            "instrument_info": {
                "pClosing": closing if closing is not None else last,
                "pDrCotVal": last if last is not None else closing,
                "priceYesterday": previous,
                "priceMax": number(first(row, "priceMax", "pMax")),
                "priceMin": number(first(row, "priceMin", "pMin")),
                "qTotTran5J": number(first(row, "qTotTran5J", "volume")),
                "hEven": first(row, "hEven", "heven") or "",
                "quoteStatus": "ACTIVE",
            },
            "daily": [], "client_type_history": [], "major_shareholders": [],
            "codal_filings": [], "statement_content": [], "share_changes": [],
        }
        symbols[symbol] = item
    if len(symbols) < 1000:
        raise RuntimeError(f"CDN returned only {len(symbols)} symbols")
    return symbols, "tsetmc-cdn-marketwatch", []


def main():
    session = requests.Session()
    session.headers.update(HEADERS)
    try:
        symbols, source, errors = fetch_webgw(session)
    except Exception as webgw_error:
        try:
            symbols, source, errors = fetch_cdn(session)
            errors.append(f"webgw fallback: {webgw_error}")
        except Exception as cdn_error:
            raise RuntimeError(f"All full-market sources failed: webgw={webgw_error}; cdn={cdn_error}") from cdn_error

    now_tehran = datetime.now(ZoneInfo("Asia/Tehran"))
    market_status = "OPEN" if now_tehran.weekday() in {5, 6, 0, 1, 2} and 9 <= now_tehran.hour < 13 else "CLOSED"
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "market_status": market_status,
        "universe_mode": "FULL_MARKET",
        "universe_count": len(symbols),
        "symbols": symbols,
        "errors": {"fetch": errors} if errors else {},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Full-Market mirror created: {len(symbols)} symbols")
    print(f"Source: {source}")
    print(f"Generated at: {payload['generated_at']}")


if __name__ == "__main__":
    main()
