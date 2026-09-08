from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

# Railway cannot reliably reach TSETMC directly. GitHub Actions is the
# external collector. Prefer the legacy bulk MarketWatch feed so one request
# supplies the whole market instead of many fragile per-symbol CDN calls.
MARKETWATCH_URLS = [
    os.getenv("IEA_TSETMC_MARKETWATCH_URL", "https://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx"),
    "http://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx",
    "https://members.tsetmc.com/tsev2/data/MarketWatchPlus.aspx",
]
SYMBOLS = ["فولاد", "فملی", "شستا", "خودرو", "وبملت"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "text/plain,text/*,*/*",
    "Referer": "https://www.tsetmc.com/",
    "Origin": "https://www.tsetmc.com",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


def number(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_marketwatch() -> tuple[dict[str, list[str]], str]:
    last_error: Exception | None = None
    for url in MARKETWATCH_URLS:
        for attempt in range(3):
            try:
                response = requests.get(url, headers=HEADERS, timeout=25)
                response.raise_for_status()
                text = response.content.decode("utf-8-sig", errors="ignore")
                parts = text.split("@")
                if len(parts) < 3:
                    raise RuntimeError("response has no quote section")

                rows: dict[str, list[str]] = {}
                for raw in parts[2].split(";"):
                    fields = raw.split(",")
                    if len(fields) >= 23 and fields[2].strip():
                        rows[fields[2].strip()] = fields
                if rows:
                    return rows, url
                raise RuntimeError("no instrument rows returned")
            except (requests.RequestException, RuntimeError) as exc:
                last_error = exc
                if attempt < 2:
                    time.sleep(1 + attempt * 2)
    raise RuntimeError(f"all TSETMC legacy endpoints failed: {last_error}")


def main() -> None:
    output = Path("data/iran_market_live.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    requested = [x.strip() for x in os.getenv("IEA_IR_SYMBOLS", ",".join(SYMBOLS)).split(",") if x.strip()]
    rows, source_url = fetch_marketwatch()
    symbols: dict[str, dict] = {}
    errors: dict[str, str] = {}
    generated_at = datetime.now(timezone.utc).isoformat()

    for symbol in requested:
        fields = rows.get(symbol)
        if fields is None:
            errors[symbol] = "symbol not present in legacy MarketWatch"
            continue
        # Legacy MarketWatch fields:
        # 2=ticker, 6=last/close, 9=volume, 11=low, 12=high, 13=yesterday.
        price = number(fields[6])
        previous = number(fields[13])
        if price is None:
            errors[symbol] = "price missing in legacy MarketWatch row"
            continue
        symbols[symbol] = {
            "instrument": {"lVal18AFC": symbol},
            "instrument_info": {
                "pClosing": price,
                "pDrCotVal": price,
                "priceYesterday": previous,
                "qTotTran5J": number(fields[9]),
                "priceMax": number(fields[12]),
                "priceMin": number(fields[11]),
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
        "source": f"tsetmc-legacy-marketwatch-via-github-actions:{source_url}",
        "market_status": "LIVE_OR_CLOSED_FROM_TSETMC_FEED",
        "symbols": symbols,
        "errors": errors,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    if not symbols:
        raise SystemExit("No requested Iran market symbols were collected")
    print(f"Published {len(symbols)}/{len(requested)} requested Iran market symbols")
    for symbol, row in symbols.items():
        info = row["instrument_info"]
        print(f"{symbol}: price={info['pClosing']} previous={info['priceYesterday']} volume={info['qTotTran5J']}")
    if errors:
        print("Missing symbols:", ", ".join(sorted(errors)))


if __name__ == "__main__":
    main()
