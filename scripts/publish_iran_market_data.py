from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import requests

CDN_MARKETWATCH_URL = "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
LEGACY_MARKETWATCH_URL = "https://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx"
SYMBOLS = ["فولاد", "فملی", "شستا", "خودرو", "وبملت"]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.tsetmc.com/",
    "Origin": "https://www.tsetmc.com",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}

CDN_PARAMS = {
    "market": "0",
    "industrialGroup": "",
    "paperTypes[0]": "1",
    "paperTypes[1]": "2",
    "paperTypes[2]": "3",
    "paperTypes[3]": "4",
    "paperTypes[4]": "5",
    "paperTypes[5]": "6",
    "paperTypes[6]": "7",
    "paperTypes[7]": "8",
    "paperTypes[8]": "9",
    "showTraded": "false",
    "withBestLimits": "false",
    "hEven": "0",
    "RefID": "0",
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


def fetch_cdn_marketwatch() -> tuple[dict[str, dict[str, Any]], str]:
    last_error: Exception | None = None
    for attempt in range(3):
        try:
            response = requests.get(
                CDN_MARKETWATCH_URL,
                params=CDN_PARAMS,
                headers=HEADERS,
                timeout=(10, 30),
            )
            response.raise_for_status()
            payload = response.json()
            rows = payload.get("marketwatch") if isinstance(payload, dict) else payload
            if not isinstance(rows, list) or not rows:
                raise RuntimeError("TSETMC CDN marketwatch response contains no rows")
            parsed: dict[str, dict[str, Any]] = {}
            for row in rows:
                if not isinstance(row, dict):
                    continue
                symbol = normalize_symbol(row.get("l18") or row.get("lVal18AFC") or row.get("symbol") or row.get("ticker"))
                if symbol:
                    parsed[symbol] = row
            if not parsed:
                raise RuntimeError("TSETMC CDN marketwatch returned no named instruments")
            return parsed, CDN_MARKETWATCH_URL
        except (requests.RequestException, ValueError, RuntimeError) as exc:
            last_error = exc
            if attempt < 2:
                time.sleep(2 ** attempt)
    raise RuntimeError(f"TSETMC CDN marketwatch failed: {last_error}")


def fetch_legacy_marketwatch() -> tuple[dict[str, dict[str, Any]], str]:
    response = requests.get(LEGACY_MARKETWATCH_URL, headers=HEADERS, timeout=(10, 20))
    response.raise_for_status()
    text = response.content.decode("utf-8-sig", errors="ignore")
    parts = text.split("@")
    if len(parts) < 3:
        raise RuntimeError("legacy MarketWatch response has no quote section")
    rows: dict[str, dict[str, Any]] = {}
    for raw in parts[2].split(";"):
        fields = raw.split(",")
        if len(fields) >= 14 and fields[2].strip():
            symbol = fields[2].strip()
            rows[symbol] = {"l18": symbol, "pc": fields[6], "py": fields[13], "tvol": fields[9], "pmin": fields[11], "pmax": fields[12]}
    if not rows:
        raise RuntimeError("legacy MarketWatch returned no instrument rows")
    return rows, LEGACY_MARKETWATCH_URL


def fetch_marketwatch() -> tuple[dict[str, dict[str, Any]], str]:
    try:
        return fetch_cdn_marketwatch()
    except Exception as cdn_error:
        try:
            return fetch_legacy_marketwatch()
        except Exception as legacy_error:
            raise RuntimeError(
                "all TSETMC collector paths failed; "
                f"cdn={type(cdn_error).__name__}: {cdn_error}; "
                f"legacy={type(legacy_error).__name__}: {legacy_error}"
            ) from legacy_error


def main() -> None:
    output = Path("data/iran_market_live.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    requested = [x.strip() for x in os.getenv("IEA_IR_SYMBOLS", ",".join(SYMBOLS)).split(",") if x.strip()]
    rows, source_url = fetch_marketwatch()
    symbols: dict[str, dict[str, Any]] = {}
    errors: dict[str, str] = {}
    generated_at = datetime.now(timezone.utc).isoformat()

    for symbol in requested:
        row = rows.get(symbol)
        if row is None:
            row = next((v for k, v in rows.items() if normalize_symbol(k) == normalize_symbol(symbol)), None)
        if row is None:
            errors[symbol] = "symbol not present in TSETMC marketwatch"
            continue
        price = number(row.get("pc", row.get("pClosing")))
        last = number(row.get("pl", row.get("pDrCotVal", price)))
        previous = number(row.get("py", row.get("priceYesterday")))
        if price is None and last is not None:
            price = last
        if price is None:
            errors[symbol] = "closing/last price missing in TSETMC marketwatch row"
            continue
        symbols[symbol] = {
            "instrument": {"lVal18AFC": symbol, "insCode": row.get("insCode") or row.get("ins_code")},
            "instrument_info": {
                "pClosing": price,
                "pDrCotVal": last if last is not None else price,
                "priceYesterday": previous,
                "qTotTran5J": number(row.get("tvol", row.get("qTotTran5J"))),
                "priceMax": number(row.get("pmax", row.get("priceMax"))),
                "priceMin": number(row.get("pmin", row.get("priceMin"))),
            },
            "daily": [],
            "client_type_history": [],
            "major_shareholders": [],
            "codal_filings": [],
            "statement_content": [],
            "share_changes": [],
        }

    payload = {
        "generated_at": generated_at,
        "source": f"tsetmc-cdn-marketwatch-via-github-actions:{source_url}",
        "market_status": "LIVE_OR_CLOSED_FROM_TSETMC_FEED",
        "symbols": symbols,
        "errors": errors,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    if len(symbols) != len(requested):
        missing = ", ".join(sorted(set(requested) - set(symbols)))
        raise SystemExit(f"TSETMC mirror incomplete: collected {len(symbols)}/{len(requested)}; missing={missing}")

    print(f"Published {len(symbols)}/{len(requested)} requested Iran market symbols")
    for symbol, row in symbols.items():
        info = row["instrument_info"]
        print(f"{symbol}: price={info['pClosing']} previous={info['priceYesterday']} volume={info['qTotTran5J']}")


if __name__ == "__main__":
    main()
