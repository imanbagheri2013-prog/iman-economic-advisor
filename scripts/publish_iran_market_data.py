from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import requests

# Railway cannot reliably reach the modern TSETMC CDN. GitHub Actions is used
# as the external collector, and the legacy bulk MarketWatch feed gives all
# instruments in one request, avoiding dozens of fragile per-symbol CDN calls.
MARKETWATCH_URL = os.getenv(
    "IEA_TSETMC_MARKETWATCH_URL",
    "http://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx",
)
SYMBOLS = ["فولاد", "فملی", "شستا", "خودرو", "وبملت"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "text/plain,text/*,*/*",
    "Referer": "http://old.tsetmc.com/",
}


def number(value: str):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_marketwatch() -> dict[str, list[str]]:
    response = requests.get(MARKETWATCH_URL, headers=HEADERS, timeout=30)
    response.raise_for_status()
    text = response.content.decode("utf-8", errors="ignore")
    parts = text.split("@")
    if len(parts) < 3:
        raise RuntimeError("TSETMC legacy MarketWatch response has no quote section")

    rows: dict[str, list[str]] = {}
    # MarketWatchPlus section 2 is the instrument quote table.
    for raw in parts[2].split(";"):
        fields = raw.split(",")
        if len(fields) >= 23 and fields[2].strip():
            rows[fields[2].strip()] = fields
    if not rows:
        raise RuntimeError("TSETMC legacy MarketWatch returned no instrument rows")
    return rows


def main() -> None:
    output = Path("data/iran_market_live.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    requested = [x.strip() for x in os.getenv("IEA_IR_SYMBOLS", ",".join(SYMBOLS)).split(",") if x.strip()]
    rows = fetch_marketwatch()
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
        "source": "tsetmc-legacy-marketwatch-via-github-actions",
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
