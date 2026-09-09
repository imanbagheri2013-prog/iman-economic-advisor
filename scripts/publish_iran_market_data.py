from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode
from zoneinfo import ZoneInfo

import requests

TINDEX_BASE = "https://tindex.app/stocks/"
TSE_PUBLIC_JSON_URL = "https://tse.ir/json/MarketWatch/data_7.json"
CDN_MARKETWATCH_URL = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
LEGACY_MARKETWATCH_URL = "https://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx"
SYMBOLS = ["فولاد", "فملی", "شستا", "خودرو", "وبملت"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36", "Accept": "text/html,application/json,text/plain,*/*"}
CDN_PARAMS = {"market": "0", "industrialGroup": "", "paperTypes[0]": "1", "paperTypes[1]": "2", "paperTypes[2]": "3", "paperTypes[3]": "4", "paperTypes[4]": "5", "paperTypes[5]": "6", "paperTypes[6]": "7", "paperTypes[7]": "8", "paperTypes[8]": "9", "showTraded": "false", "withBestLimits": "false", "hEven": "0", "RefID": "0"}

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
PERSIAN_MONTHS = r"فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند"


def normalize_digits(value: Any) -> str:
    return str(value or "").translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS)


def number(value: Any) -> float | None:
    try:
        if value in (None, "", "-"):
            return None
        text = normalize_digits(value).replace("٬", "").replace(",", "").replace("٫", ".").replace(" ", "")
        return float(text)
    except (TypeError, ValueError):
        return None


def normalize_symbol(value: Any) -> str:
    return str(value or "").strip().replace("\u200c", "")


def html_text(html: str) -> str:
    text = re.sub(r"<script[^>]*>.*?</script>", " ", html, flags=re.I | re.S)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.I | re.S)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", unescape(text)).strip()


def parse_scaled_number(raw: str | None, unit: str | None) -> float | None:
    value = number(raw)
    if value is None:
        return None
    multipliers = {"میلیون": 1_000_000.0, "میلیارد": 1_000_000_000.0, "هزار": 1_000.0}
    return value * multipliers.get(unit or "", 1.0)


def fetch_tindex_history(session: requests.Session, symbol: str) -> tuple[float | None, str | None]:
    url = TINDEX_BASE + quote(symbol, safe="") + "/history/"
    response = session.get(url, headers=HEADERS, timeout=(4, 8))
    response.raise_for_status()
    text = html_text(response.text)
    marker = "تاریخ  | بازگشایی  | بیشترین  | کمترین  | پایانی  | تغییر"
    if marker not in text:
        return None, None
    tail = text.split(marker, 1)[1]
    row_pattern = re.compile(
        rf"((?:[۰-۹0-9]{{1,2}})\s+(?:{PERSIAN_MONTHS})\s+[۰-۹0-9]{{4}})\s*\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)\|\s*([^|]+)"
    )
    rows: list[tuple[str, float]] = []
    for match in row_pattern.finditer(tail):
        closing = number(match.group(5))
        if closing is not None and closing > 0:
            rows.append((match.group(1).strip(), closing))
    if not rows:
        return None, None
    # The first valid row is today's trading row when the symbol traded today.
    # Otherwise it is the latest prior trading day. In both cases, the previous
    # close is the next valid historical row when available; for a currently
    # suspended/no-trade symbol the latest valid row is the safest reference.
    if len(rows) >= 2:
        return rows[1][1], rows[1][0]
    return rows[0][1], rows[0][0]


def fetch_tindex(requested: list[str]) -> tuple[dict[str, dict[str, Any]], str]:
    rows: dict[str, dict[str, Any]] = {}
    session = requests.Session()
    session.headers.update(HEADERS)
    for symbol in requested:
        url = TINDEX_BASE + quote(symbol, safe="") + "/"
        response = session.get(url, headers=HEADERS, timeout=(4, 8))
        response.raise_for_status()
        text = html_text(response.text)
        last_match = re.search(r"آخرین قیمت\s*([0-9۰-۹٬,]+)\s*ریال", text)
        close_match = re.search(r"قیمت پایانی\s*([0-9۰-۹٬,]+)\s*ریال", text)
        volume_match = re.search(r"حجم\s*([0-9۰-۹٬,.]+)\s*(هزار|میلیون|میلیارد)?", text)
        if not last_match and not close_match:
            raise RuntimeError(f"Tindex returned no live price for {symbol}")
        previous, previous_date = fetch_tindex_history(session, symbol)
        volume = parse_scaled_number(volume_match.group(1), volume_match.group(2)) if volume_match else None
        rows[symbol] = {
            "l18": symbol,
            "pl": last_match.group(1) if last_match else close_match.group(1),
            "pc": close_match.group(1) if close_match else last_match.group(1),
            "py": previous,
            "previous_date": previous_date,
            "volume": volume,
            "quote_status": "ACTIVE" if volume is not None and volume > 0 else "SUSPENDED_OR_NO_TRADE",
            "source": "tindex",
        }
    return rows, "tindex-live"


def flatten_json(obj: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    if isinstance(obj, dict):
        out.append(obj)
        for value in obj.values():
            out.extend(flatten_json(value))
    elif isinstance(obj, list):
        for value in obj:
            out.extend(flatten_json(value))
    return out


def parse_tse_public_json(text: str) -> dict[str, dict[str, Any]]:
    data = json.loads(text.lstrip("\ufeff"))
    rows: dict[str, dict[str, Any]] = {}
    for item in flatten_json(data):
        symbol = normalize_symbol(item.get("l18") or item.get("lVal18AFC") or item.get("symbol") or item.get("ticker") or item.get("sy") or item.get("s"))
        if symbol:
            rows[symbol] = item
    if not rows:
        raise RuntimeError("TSE public JSON contained no named market rows")
    return rows


def parse_cdn(text: str) -> dict[str, dict[str, Any]]:
    payload = json.loads(text.lstrip("\ufeff"))
    rows = payload.get("marketwatch") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("empty CDN marketwatch")
    return {normalize_symbol(r.get("l18") or r.get("lVal18AFC") or r.get("symbol") or r.get("ticker")): r for r in rows if isinstance(r, dict) and normalize_symbol(r.get("l18") or r.get("lVal18AFC") or r.get("symbol") or r.get("ticker"))}


def parse_legacy(text: str) -> dict[str, dict[str, Any]]:
    parts = text.split("@")
    if len(parts) < 3:
        raise RuntimeError("empty legacy marketwatch")
    rows: dict[str, dict[str, Any]] = {}
    for raw in parts[2].split(";"):
        f = raw.split(",")
        if len(f) >= 14 and f[2].strip():
            rows[f[2].strip()] = {"l18": f[2].strip(), "pc": f[6], "py": f[13], "tvol": f[9], "pmin": f[11], "pmax": f[12]}
    if not rows:
        raise RuntimeError("legacy marketwatch has no rows")
    return rows


def fetch_marketwatch(requested: list[str]) -> tuple[dict[str, dict[str, Any]], str]:
    try:
        return fetch_tindex(requested)
    except Exception as exc:
        failures = [f"tindex/{type(exc).__name__}: {exc}"]
    targets = [(TSE_PUBLIC_JSON_URL, "tse-public-json"), (f"https://api.allorigins.win/raw?url={quote(CDN_MARKETWATCH_URL+'?'+urlencode(CDN_PARAMS), safe='')}", "tsetmc-cdn-via-allorigins"), (CDN_MARKETWATCH_URL, "tsetmc-cdn-direct"), (LEGACY_MARKETWATCH_URL, "tsetmc-legacy-direct")]
    for url, source in targets:
        try:
            response = requests.get(url, headers=HEADERS, params=CDN_PARAMS if source == "tsetmc-cdn-direct" else None, timeout=(4, 8))
            response.raise_for_status()
            if source == "tse-public-json":
                return parse_tse_public_json(response.text), source
            if "cdn" in source:
                return parse_cdn(response.text), source
            return parse_legacy(response.text), source
        except Exception as exc:
            failures.append(f"{source}/{type(exc).__name__}: {exc}")
    raise RuntimeError("all Iran market sources failed: " + " | ".join(failures))


def market_status() -> str:
    now = datetime.now(ZoneInfo("Asia/Tehran"))
    if now.weekday() in {5, 6, 0, 1, 2} and 9 <= now.hour + now.minute / 60 < 12.5:
        return "OPEN"
    return "CLOSED"


def main() -> None:
    output = Path("data/iran_market_live.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    requested = [x.strip() for x in os.getenv("IEA_IR_SYMBOLS", ",".join(SYMBOLS)).split(",") if x.strip()]
    rows, source = fetch_marketwatch(requested)
    symbols: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for symbol in requested:
        row = rows.get(symbol) or next((v for k, v in rows.items() if normalize_symbol(k) == normalize_symbol(symbol)), None)
        if row is None:
            errors[symbol] = "symbol not present"
            continue
        price = number(row.get("pc", row.get("pClosing", row.get("closingPrice", row.get("close", row.get("Close"))))))
        last = number(row.get("pl", row.get("pDrCotVal", row.get("lastPrice", row.get("last", row.get("Last", price))))))
        previous = number(row.get("py", row.get("priceYesterday", row.get("yesterdayPrice", row.get("previousClose")))))
        volume = number(row.get("volume", row.get("tvol", row.get("qTotTran5J", row.get("tradeVolume", row.get("volume_raw"))))))
        high = number(row.get("pmax", row.get("priceMax", row.get("highValue", row.get("high", row.get("High"))))))
        low = number(row.get("pmin", row.get("priceMin", row.get("lowValue", row.get("low", row.get("Low"))))))
        if price is None and last is not None:
            price = last
        if price is None:
            errors[symbol] = "price missing"
            continue
        quote_status = row.get("quote_status") or ("ACTIVE" if volume is not None and volume > 0 else "SUSPENDED_OR_NO_TRADE")
        symbols[symbol] = {
            "instrument": {"lVal18AFC": symbol, "insCode": row.get("insCode") or row.get("ins_code")},
            "instrument_info": {
                "pClosing": price, "pDrCotVal": last or price, "priceYesterday": previous,
                "qTotTran5J": volume, "priceMax": high, "priceMin": low,
                "previousDate": row.get("previous_date"), "quoteStatus": quote_status,
            },
            "daily": [], "client_type_history": [], "major_shareholders": [],
            "codal_filings": [], "statement_content": [], "share_changes": [],
        }
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "source": f"{source}:github-actions", "market_status": market_status(), "symbols": symbols, "errors": errors}
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if len(symbols) != len(requested):
        raise SystemExit(f"Iran market mirror incomplete: collected {len(symbols)}/{len(requested)}; missing={','.join(sorted(set(requested)-set(symbols)))}")
    # A symbol may legitimately have no previous close when it has just been
    # suspended, is under a corporate-action halt, or has not traded yet.
    # The mirror must remain publishable; that individual symbol is fail-closed
    # by the analysis layer rather than invalidating all other symbols.
    missing_previous = [symbol for symbol, row in symbols.items() if row["instrument_info"].get("priceYesterday") is None]
    if missing_previous:
        print("Symbols without previous close (individual NO_TRADE): " + ",".join(missing_previous))
    print(f"Published {len(symbols)}/{len(requested)} requested Iran market symbols via {source}")
    for symbol, row in symbols.items():
        info = row["instrument_info"]
        print(f"{symbol}: price={info['pClosing']} last={info['pDrCotVal']} previous={info['priceYesterday']} volume={info['qTotTran5J']} status={info['quoteStatus']}")


if __name__ == "__main__":
    main()
