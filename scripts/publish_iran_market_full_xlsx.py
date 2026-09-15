from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from zoneinfo import ZoneInfo

import requests

OUT = Path("data/iran_market_live.json")
BASE = "https://webgw.tse.ir/InstrumentProvider/api/v1/MarketWatch"
ENDPOINTS = {k: f"{BASE}/{v}/fa" for k, v in {"cash":"MarketWatchCash","etf":"MarketWatchEtf","future":"MarketWatchFuture","option":"MarketWatchOption","debt":"MarketWatchDebt"}.items()}
CDN_URL = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch?market=0&industrialGroup=&paperTypes%5B0%5D=1&paperTypes%5B1%5D=2&paperTypes%5B2%5D=3&paperTypes%5B3%5D=4&paperTypes%5B4%5D=5&paperTypes%5B5%5D=6&paperTypes%5B6%5D=7&paperTypes%5B7%5D=8&paperTypes%5B8%5D=9&showTraded=false&withBestLimits=false&hEven=0&RefID=0"
HEADERS = {"User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36", "Accept":"application/json,text/plain,*/*", "Referer":"https://www.tse.ir/"}


def value(v):
    if isinstance(v, dict):
        return v.get("value", v.get("Value"))
    return v


def first(row, *names):
    if not isinstance(row, dict):
        return None
    keys = {str(k).lower(): k for k in row}
    for name in names:
        k = keys.get(name.lower())
        if k is not None:
            v = value(row[k])
            if v not in (None, "", "-"):
                return v
    return None


def number(v):
    if v in (None, "", "-"):
        return None
    try:
        return float(str(value(v)).replace(",", "").replace("٬", "").replace("٫", "."))
    except (TypeError, ValueError):
        return None


def build_item(row):
    symbol = str(first(row, "instrumentName", "instrument_Name", "lVal18AFC", "lVal18AfC", "symbol", "name") or "").strip()
    isin = str(first(row, "instrumentId", "instrumentid", "isin", "ISIN", "insCode", "inscode") or "").strip()
    key = isin or symbol
    if not key:
        return None
    closing = number(first(row, "closingPrice", "pClosing", "closing", "closePrice"))
    last = number(first(row, "lastPrice", "pDrCotVal", "last", "tradePrice"))
    previous = number(first(row, "yesterdayPrice", "priceYesterday", "py", "previousPrice"))
    volume = number(first(row, "tradeVolume", "qTotTran5J", "volume", "totalVolume"))
    return {"instrument":{"lVal18AFC":symbol or key,"insCode":first(row,"insCode","inscode"),"isin":isin or None},"instrument_info":{"pClosing":closing,"pDrCotVal":last,"priceYesterday":previous,"priceMax":number(first(row,"maxValue","priceMax","pMax")),"priceMin":number(first(row,"minValue","priceMin","pMin")),"qTotTran5J":volume,"hEven":first(row,"hEven","heven") or "","quoteStatus":"ACTIVE" if volume not in (None,0) else "SUSPENDED_OR_NO_TRADE"},"market":{"marketId":first(row,"marketid","marketId"),"marketName":first(row,"marketname","marketName"),"marketType":first(row,"markettypeid","marketTypeId","markettypename","marketTypeName"),"industry":first(row,"industryid","industryId","industryname","industryName"),"state":first(row,"stateid","stateId","statename","stateName")},"daily":[],"client_type_history":[],"major_shareholders":[],"codal_filings":[],"statement_content":[],"share_changes":[]}


def fetch_webgw(session):
    symbols, counts, errors = {}, {}, []
    for kind, url in ENDPOINTS.items():
        try:
            r = session.get(url, timeout=(8,30), headers=HEADERS)
            r.raise_for_status()
            payload = r.json()
            rows = payload.get("Items", []) if isinstance(payload, dict) else []
            if not isinstance(rows, list):
                raise RuntimeError("Items is not a list")
            valid = 0
            for row in rows:
                item = build_item(row)
                if item:
                    key = item["instrument"].get("isin") or item["instrument"]["lVal18AFC"]
                    symbols[key] = item
                    valid += 1
            counts[kind] = {"raw":len(rows),"valid":valid}
        except Exception as exc:
            counts[kind] = {"raw":0,"valid":0}
            errors.append(f"{kind}: {type(exc).__name__}: {exc}")
    if len(symbols) >= 1000:
        return symbols, f"tse-webgw-marketwatch:{counts}", errors
    raise RuntimeError(f"webgw returned only {len(symbols)} valid symbols; counts={counts}; errors={errors}")


def fetch_cdn(session):
    r = session.get(CDN_URL, timeout=(8,30), headers=HEADERS)
    r.raise_for_status()
    payload = r.json()
    rows = payload.get("marketwatch", []) if isinstance(payload, dict) else []
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("CDN marketwatch is empty")
    symbols = {}
    for row in rows:
        item = build_item(row)
        if item:
            key = item["instrument"].get("isin") or item["instrument"]["lVal18AFC"]
            symbols[key] = item
    if len(symbols) < 1000:
        raise RuntimeError(f"CDN returned only {len(symbols)} symbols")
    return symbols, "tsetmc-cdn-marketwatch", []


def main():
    session = requests.Session()
    session.trust_env = True
    session.headers.update(HEADERS)
    try:
        symbols, source, errors = fetch_webgw(session)
    except Exception as webgw_error:
        try:
            symbols, source, errors = fetch_cdn(session)
            errors.append(f"webgw fallback: {webgw_error}")
        except Exception as cdn_error:
            raise RuntimeError(f"All full-market sources failed: webgw={webgw_error}; cdn={cdn_error}") from cdn_error
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    status = "OPEN" if now.weekday() in {5,6,0,1,2} and 9 <= now.hour < 13 else "CLOSED"
    payload = {"generated_at":datetime.now(timezone.utc).isoformat(),"source":source,"market_status":status,"universe_mode":"FULL_MARKET","universe_count":len(symbols),"symbols":symbols,"errors":{"fetch":errors} if errors else {}}
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",",":")), encoding="utf-8")
    print(f"Full-Market mirror created: {len(symbols)} symbols")
    print(f"Source: {source}")
    print(f"Generated at: {payload['generated_at']}")


if __name__ == "__main__":
    main()
