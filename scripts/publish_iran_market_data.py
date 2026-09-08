from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import quote, urlencode

import requests

CDN_MARKETWATCH_URL = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
LEGACY_MARKETWATCH_URL = "https://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx"
SYMBOLS = ["فولاد", "فملی", "شستا", "خودرو", "وبملت"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.tsetmc.com/",
    "Origin": "https://www.tsetmc.com",
}

CDN_PARAMS = {
    "market": "0", "industrialGroup": "",
    "paperTypes[0]": "1", "paperTypes[1]": "2", "paperTypes[2]": "3",
    "paperTypes[3]": "4", "paperTypes[4]": "5", "paperTypes[5]": "6",
    "paperTypes[6]": "7", "paperTypes[7]": "8", "paperTypes[8]": "9",
    "showTraded": "false", "withBestLimits": "false", "hEven": "0", "RefID": "0",
}


def number(value: Any) -> float | None:
    try:
        if value in (None, "", "-"):
            return None
        return float(value)
    except (TypeError, ValueError):
        return None


def normalize_symbol(value: Any) -> str:
    return str(value or "").strip().replace("\u200c", "")


def parse_cdn(text: str) -> dict[str, dict[str, Any]]:
    payload = json.loads(text.lstrip("\ufeff"))
    rows = payload.get("marketwatch") if isinstance(payload, dict) else payload
    if not isinstance(rows, list) or not rows:
        raise RuntimeError("empty CDN marketwatch")
    parsed: dict[str, dict[str, Any]] = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = normalize_symbol(row.get("l18") or row.get("lVal18AFC") or row.get("symbol") or row.get("ticker"))
        if symbol:
            parsed[symbol] = row
    if not parsed:
        raise RuntimeError("CDN marketwatch has no named rows")
    return parsed


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


def get(url: str) -> requests.Response:
    response = requests.get(url, headers=HEADERS, timeout=(5, 8))
    response.raise_for_status()
    return response


def fetch_marketwatch() -> tuple[dict[str, dict[str, Any]], str]:
    target_cdn = f"{CDN_MARKETWATCH_URL}?{urlencode(CDN_PARAMS)}"
    target_legacy = LEGACY_MARKETWATCH_URL
    targets = [
        (f"https://api.allorigins.win/raw?url={quote(target_cdn, safe='')}", "tsetmc-cdn-via-allorigins"),
        (f"https://api.codetabs.com/v1/proxy?quest={quote(target_cdn, safe='')}", "tsetmc-cdn-via-codetabs"),
        (target_cdn, "tsetmc-cdn-direct"),
        (f"https://api.allorigins.win/raw?url={quote(target_legacy, safe='')}", "tsetmc-legacy-via-allorigins"),
        (target_legacy, "tsetmc-legacy-direct"),
    ]
    failures: list[str] = []
    for url, source in targets:
        try:
            text = get(url).text
            rows = parse_cdn(text) if "cdn" in source else parse_legacy(text)
            return rows, source
        except Exception as exc:
            failures.append(f"{source}/{type(exc).__name__}: {exc}")
            time.sleep(0.5)
    raise RuntimeError("all TSETMC sources failed: " + " | ".join(failures))


def main() -> None:
    output = Path("data/iran_market_live.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    requested = [x.strip() for x in os.getenv("IEA_IR_SYMBOLS", ",".join(SYMBOLS)).split(",") if x.strip()]
    rows, source = fetch_marketwatch()
    symbols: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    for symbol in requested:
        row = rows.get(symbol) or next((v for k, v in rows.items() if normalize_symbol(k) == normalize_symbol(symbol)), None)
        if row is None:
            errors[symbol] = "symbol not present"
            continue
        price = number(row.get("pc", row.get("pClosing")))
        last = number(row.get("pl", row.get("pDrCotVal", price)))
        previous = number(row.get("py", row.get("priceYesterday")))
        if price is None and last is not None:
            price = last
        if price is None:
            errors[symbol] = "price missing"
            continue
        symbols[symbol] = {
            "instrument": {"lVal18AFC": symbol, "insCode": row.get("insCode") or row.get("ins_code")},
            "instrument_info": {"pClosing": price, "pDrCotVal": last or price, "priceYesterday": previous,
                                 "qTotTran5J": number(row.get("tvol", row.get("qTotTran5J"))),
                                 "priceMax": number(row.get("pmax", row.get("priceMax"))),
                                 "priceMin": number(row.get("pmin", row.get("priceMin")))},
            "daily": [], "client_type_history": [], "major_shareholders": [],
            "codal_filings": [], "statement_content": [], "share_changes": [],
        }
    payload = {"generated_at": datetime.now(timezone.utc).isoformat(), "source": f"{source}:github-actions",
               "market_status": "LIVE_OR_CLOSED_FROM_TSETMC_FEED", "symbols": symbols, "errors": errors}
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if len(symbols) != len(requested):
        raise SystemExit(f"TSETMC mirror incomplete: collected {len(symbols)}/{len(requested)}; missing={','.join(sorted(set(requested)-set(symbols)))}")
    print(f"Published {len(symbols)}/{len(requested)} requested Iran market symbols")
    for symbol, row in symbols.items():
        info = row["instrument_info"]
        print(f"{symbol}: price={info['pClosing']} previous={info['priceYesterday']} volume={info['qTotTran5J']}")


if __name__ == "__main__":
    main()
