from __future__ import annotations

import json
import os
import re
from datetime import datetime, timezone
from html import unescape
from pathlib import Path
from typing import Any
from urllib.parse import quote
from zoneinfo import ZoneInfo

import requests

TINDEX_BASE = "https://tindex.app/stocks/"
TSE_PUBLIC_JSON_URL = "https://tse.ir/json/MarketWatch/data_7.json"
CDN_MARKETWATCH_URL = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
LEGACY_MARKETWATCH_URL = "http://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx"
SYMBOLS = ["فولاد", "فملی", "شستا", "خودرو", "وبملت"]
HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36", "Accept": "text/html,application/json,text/plain,*/*"}

PERSIAN_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "0123456789")
ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
PERSIAN_MONTHS = r"فروردین|اردیبهشت|خرداد|تیر|مرداد|شهریور|مهر|آبان|آذر|دی|بهمن|اسفند"


def normalize_digits(value: Any) -> str:
    return str(value or "").translate(PERSIAN_DIGITS).translate(ARABIC_DIGITS)


def number(value: Any) -> float | None:
    if value in (None, "", "-"):
        return None
    try:
        return float(normalize_digits(value).replace("٬", "").replace(",", "").replace("٫", ".").replace(" ", ""))
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
    return None if value is None else value * {"هزار": 1_000.0, "میلیون": 1_000_000.0, "میلیارد": 1_000_000_000.0}.get(unit or "", 1.0)


def fetch_tindex_history(session: requests.Session, symbol: str) -> tuple[float | None, str | None]:
    response = session.get(TINDEX_BASE + quote(symbol, safe="") + "/history/", headers=HEADERS, timeout=(4, 8))
    response.raise_for_status()
    text = html_text(response.text)
    marker = "تاریخ | بازگشایی | بیشترین | کمترین | پایانی | تغییر"
    if marker not in text:
        return None, None

    tail = text.split(marker, 1)[1]
    date_pattern = re.compile(rf"[۰-۹0-9]{{1,2}}\s+(?:{PERSIAN_MONTHS})\s+[۰-۹0-9]{{4}}")
    date_matches = list(date_pattern.finditer(tail))
    rows: list[tuple[str, float | None]] = []

    # TIndex renders the history table as whitespace-separated text after
    # HTML stripping. Parse each dated row by taking the four numeric price
    # columns that follow the date; this survives changes in whitespace and
    # table-cell separators.
    for index, match in enumerate(date_matches):
        segment_end = date_matches[index + 1].start() if index + 1 < len(date_matches) else len(tail)
        segment = tail[match.end():segment_end]
        numeric_tokens = re.findall(r"[۰-۹0-9][۰-۹0-9٬,٫.]*", segment)
        close = number(numeric_tokens[3]) if len(numeric_tokens) >= 4 else None
        rows.append((match.group(0), close))

    if not rows:
        return None, None

    positive = [(date, close) for date, close in rows if close is not None and close > 0]
    if not positive:
        return None, None

    # If today's row traded, the next positive row is yesterday's close.
    # If today's row is a suspension/no-trade row (close=0), the first
    # positive row is already the latest valid prior trading close.
    first_close = rows[0][1]
    if first_close is not None and first_close > 0:
        return (positive[1] if len(positive) >= 2 else positive[0])
    return positive[0]


def fetch_tindex(requested: list[str]) -> tuple[dict[str, dict[str, Any]], str]:
    rows: dict[str, dict[str, Any]] = {}
    session = requests.Session()
    session.headers.update(HEADERS)
    for symbol in requested:
        response = session.get(TINDEX_BASE + quote(symbol, safe="") + "/", headers=HEADERS, timeout=(4, 8))
        response.raise_for_status()
        text = html_text(response.text)
        last_match = re.search(r"آخرین قیمت\s*([0-9۰-۹٬,]+)\s*ریال", text)
        close_match = re.search(r"قیمت پایانی\s*([0-9۰-۹٬,]+)\s*ریال", text)
        volume_match = re.search(r"حجم\s*([0-9۰-۹٬,.]+)\s*(هزار|میلیون|میلیارد)?", text)
        if not last_match and not close_match:
            raise RuntimeError(f"Tindex returned no live price for {symbol}")
        previous, previous_date = fetch_tindex_history(session, symbol)
        volume = parse_scaled_number(volume_match.group(1), volume_match.group(2)) if volume_match else None
        rows[symbol] = {"l18": symbol, "pl": last_match.group(1) if last_match else close_match.group(1), "pc": close_match.group(1) if close_match else last_match.group(1), "py": previous, "previous_date": previous_date, "volume": volume, "quote_status": "ACTIVE" if volume is not None and volume > 0 else "SUSPENDED_OR_NO_TRADE", "source": "tindex"}
    return rows, "tindex-live"


def flatten_json(obj: Any) -> list[dict[str, Any]]:
    if isinstance(obj, dict):
        return [obj] + sum((flatten_json(v) for v in obj.values()), [])
    if isinstance(obj, list):
        return sum((flatten_json(v) for v in obj), [])
    return []


def parse_tse_public_json(text: str) -> dict[str, dict[str, Any]]:
    data = json.loads(text.lstrip("\ufeff"))
    rows = {}
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
    rows = {}
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
    targets = [(TSE_PUBLIC_JSON_URL, "tse-public-json"), (CDN_MARKETWATCH_URL, "tsetmc-cdn-direct"), (LEGACY_MARKETWATCH_URL, "tsetmc-legacy-direct")]
    for url, source in targets:
        try:
            response = requests.get(url, headers=HEADERS, timeout=(4, 8))
            response.raise_for_status()
            if source == "tse-public-json":
                return parse_tse_public_json(response.text), source
            if "cdn" in source:
                return parse_cdn(response.text), source
            return parse_legacy(response.text), source
        except Exception as exc:
            failures.append(f"{source}/{type(exc).__name__}: {exc}")
    raise RuntimeError("all Iran market providers failed: " + " | ".join(failures))


def _number(value: Any) -> float | None:
    return number(value)


def _build_snapshot(rows: dict[str, dict[str, Any]], source: str) -> dict[str, Any]:
    generated_at = datetime.now(timezone.utc).isoformat()
    symbols: dict[str, Any] = {}
    for symbol in SYMBOLS:
        row = rows.get(symbol)
        if not row:
            continue
        symbols[symbol] = {
            "instrument": {"lVal18AFC": symbol, "insCode": row.get("insCode")},
            "instrument_info": {
                "pClosing": _number(row.get("pc") or row.get("pClosing")),
                "pDrCotVal": _number(row.get("pl") or row.get("pDrCotVal")),
                "priceYesterday": _number(row.get("py") or row.get("priceYesterday")),
                "qTotTran5J": _number(row.get("volume") or row.get("qTotTran5J") or row.get("tvol")),
                "priceMax": _number(row.get("pmax") or row.get("priceMax")),
                "priceMin": _number(row.get("pmin") or row.get("priceMin")),
                "previousDate": row.get("previous_date"),
                "quoteStatus": row.get("quote_status", "ACTIVE"),
            },
            "daily": [],
            "client_type_history": [],
            "major_shareholders": [],
            "codal_filings": [],
            "statement_content": [],
            "share_changes": [],
        }
    return {"generated_at": generated_at, "source": source, "market_status": "OPEN", "symbols": symbols, "errors": {}}


def main() -> int:
    requested = list(SYMBOLS)
    try:
        rows, source = fetch_marketwatch(requested)
        payload = _build_snapshot(rows, source)
        output = Path(os.getenv("IEA_IRAN_MARKET_OUTPUT", "data/iran_market_live.json"))
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0
    except Exception as exc:
        print(f"Iran market publisher failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
