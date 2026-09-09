from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests

TARGET = (
    "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
    "?market=0&paperTypes[0]=1&paperTypes[1]=2&paperTypes[2]=3"
    "&paperTypes[3]=4&paperTypes[4]=5&paperTypes[5]=6"
    "&paperTypes[6]=7&paperTypes[7]=8&paperTypes[8]=9"
    "&showTraded=false&withBestLimits=false&hEven=0&RefID=0"
)
PROXIES = [
    "https://api.codetabs.com/v1/proxy?quest=" + quote(TARGET, safe=""),
    "https://api.allorigins.win/raw?url=" + quote(TARGET, safe=""),
    "https://r.jina.ai/http://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
    "?market=0&paperTypes[0]=1&paperTypes[1]=2&paperTypes[2]=3"
    "&paperTypes[3]=4&paperTypes[4]=5&paperTypes[5]=6"
    "&paperTypes[6]=7&paperTypes[7]=8&paperTypes[8]=9"
    "&showTraded=false&withBestLimits=false&hEven=0&RefID=0",
]
OUT = Path("data/iran_market_live.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
}


def num(value):
    if value in (None, "", "-"):
        return None
    try:
        text = str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        return float(text.replace(",", "").replace("٬", "").replace("٫", "."))
    except (TypeError, ValueError):
        return None


def first(row, *names):
    for name in names:
        value = row.get(name)
        if value not in (None, "", "-"):
            return value
    return None


def parse(content: str):
    payload = json.loads(content.lstrip("\ufeff"))
    rows = payload.get("marketwatch") if isinstance(payload, dict) else None
    if not isinstance(rows, list):
        raise RuntimeError("proxy response has no marketwatch array")

    symbols = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(first(row, "lVal18AFC", "lVal18AfC", "l18", "symbol", "ticker") or "").strip()
        if not symbol:
            continue
        closing = num(first(row, "pClosing", "pc", "closingPrice", "close"))
        last = num(first(row, "pDrCotVal", "pl", "lastPrice", "last")) or closing
        previous = num(first(row, "priceYesterday", "py", "yesterdayPrice", "previousClose"))
        if closing is None and last is None:
            continue
        if previous is None:
            continue
        symbols[symbol] = {
            "instrument": {
                "lVal18AFC": symbol,
                "insCode": str(first(row, "insCode", "inscode", "instrumentId") or "") or None,
                "isin": first(row, "isin", "ISIN"),
            },
            "instrument_info": {
                "pClosing": closing if closing is not None else last,
                "pDrCotVal": last,
                "priceYesterday": previous,
                "priceMax": num(first(row, "priceMax", "pMax", "pmax")),
                "priceMin": num(first(row, "priceMin", "pMin", "pmin")),
                "qTotTran5J": num(first(row, "qTotTran5J", "tvol", "tradeVolume", "volume")),
                "hEven": first(row, "hEven", "heven") or "",
                "quoteStatus": "ACTIVE",
            },
            "daily": [],
            "client_type_history": [],
            "major_shareholders": [],
            "codal_filings": [],
            "statement_content": [],
            "share_changes": [],
        }
    if len(symbols) < 1000:
        raise RuntimeError(f"proxy returned only {len(symbols)} valid full-market symbols")
    return symbols


def main():
    errors = []
    session = requests.Session()
    session.headers.update(HEADERS)
    for url in PROXIES:
        try:
            response = session.get(url, timeout=(8, 45), allow_redirects=True)
            response.raise_for_status()
            symbols = parse(response.text)
            payload = {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "source": f"tsetmc-cdn-marketwatch-proxy:{url.split('/')[2]}",
                "market_status": "UNKNOWN",
                "universe_mode": "FULL_MARKET",
                "universe_count": len(symbols),
                "symbols": symbols,
                "errors": {},
            }
            OUT.parent.mkdir(parents=True, exist_ok=True)
            OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
            print(f"Proxy Full-Market mirror created: {len(symbols)} symbols")
            print(f"Source: {payload['source']}")
            return
        except Exception as exc:
            errors.append(f"{url.split('/')[2]}: {type(exc).__name__}: {exc}")
    raise RuntimeError("all Full-Market proxy sources failed: " + " | ".join(errors))


if __name__ == "__main__":
    main()
