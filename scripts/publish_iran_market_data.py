from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import requests
import urllib3.util.connection as urllib3_connection

BASE_URL = "https://cdn.tsetmc.com/api"
SYMBOLS = ["فولاد", "فملی", "شستا", "خودرو", "وبملت"]
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.tsetmc.com/",
    "Origin": "https://www.tsetmc.com",
}


def get(session: requests.Session, path: str) -> dict:
    last = None
    for attempt in range(3):
        try:
            response = session.get(f"{BASE_URL}/{path.lstrip('/')}", timeout=20)
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == 2:
                response.raise_for_status()
                payload = response.json()
                if not isinstance(payload, dict):
                    raise ValueError("non-object TSETMC response")
                return payload
        except (requests.RequestException, ValueError) as exc:
            last = exc
            if attempt == 2:
                raise
        time.sleep((1, 3)[attempt])
    raise last or RuntimeError("TSETMC request failed")


def main() -> None:
    urllib3_connection.HAS_IPV6 = False
    symbols = [x.strip() for x in os.getenv("IEA_IR_SYMBOLS", ",".join(SYMBOLS)).split(",") if x.strip()]
    output = Path("data/iran_market_live.json")
    output.parent.mkdir(parents=True, exist_ok=True)
    session = requests.Session()
    session.headers.update(HEADERS)
    generated_at = datetime.now(timezone.utc).isoformat()
    rows = {}
    errors = {}

    for symbol in symbols:
        try:
            search = get(session, f"Instrument/GetInstrumentSearch/{quote(symbol)}").get("instrumentSearch") or []
            exact = [r for r in search if str(r.get("lVal18AFC", "")).strip() == symbol]
            instrument = exact[0] if exact else (search[0] if search else None)
            if not instrument:
                raise ValueError(f"symbol not found: {symbol}")
            code = str(instrument.get("insCode") or "").strip()
            if not code:
                raise ValueError(f"InsCode missing: {symbol}")

            info = get(session, f"ClosingPrice/GetClosingPriceInfo/{code}").get("closingPriceInfo") or {}
            daily = get(session, f"ClosingPrice/GetClosingPriceDailyList/{code}/30").get("closingPriceDaily") or []
            client = get(session, f"ClientType/GetClientTypeHistory/{code}").get("clientType") or []
            shareholders = get(session, f"Shareholder/GetInstrumentShareHolderLast/{code}").get("shareHolder") or []
            codal = get(session, f"Codal/GetPreparedDataByInsCode/30/{code}").get("preparedData") or []
            content_payload = get(session, f"Codal/GetStatementContentByInsCode/{code}")
            statement_content = content_payload.get("statementContent") or content_payload.get("statementContents") or content_payload.get("data") or []
            share_changes = get(session, f"Instrument/GetInstrumentShareChange/{code}").get("instrumentShareChange") or []

            rows[symbol] = {
                "instrument": instrument,
                "instrument_info": info,
                "daily": [r for r in daily if isinstance(r, dict)][:23],
                "client_type_history": [r for r in client if isinstance(r, dict)][:23],
                "major_shareholders": [r for r in shareholders if isinstance(r, dict)],
                "codal_filings": [r for r in codal if isinstance(r, dict)],
                "statement_content": statement_content,
                "share_changes": [r for r in share_changes if isinstance(r, dict)],
            }
        except Exception as exc:
            errors[symbol] = f"{type(exc).__name__}: {exc}"

    payload = {
        "generated_at": generated_at,
        "source": "tsetmc-via-github-actions",
        "symbols": rows,
        "errors": errors,
    }
    output.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    if not rows:
        raise SystemExit("No Iran market symbols were collected")


if __name__ == "__main__":
    main()
