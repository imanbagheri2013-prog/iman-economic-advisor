from __future__ import annotations

import json
import re
import zipfile
from datetime import datetime, timezone
from io import BytesIO
from pathlib import Path
from xml.etree import ElementTree as ET
from zoneinfo import ZoneInfo

import requests

EXCEL_URLS = [
    "https://old.tsetmc.com/tsev2/excel/MarketWatchPlus.aspx?d=0",
    "https://members.tsetmc.com/tsev2/excel/MarketWatchPlus.aspx?d=0",
    "http://old.tsetmc.com/tsev2/excel/MarketWatchPlus.aspx?d=0",
    "http://members.tsetmc.com/tsev2/excel/MarketWatchPlus.aspx?d=0",
]
TEXT_URLS = [
    "https://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx",
    "http://old.tsetmc.com/tsev2/data/MarketWatchPlus.aspx",
]
CDN_MARKETWATCH_URL = (
    "https://cdn.tsetmc.com/api/ClosingPrice/GetMarketWatch"
    "?market=0&industrialGroup=&paperTypes%5B0%5D=1&paperTypes%5B1%5D=2"
    "&paperTypes%5B2%5D=3&paperTypes%5B3%5D=4&paperTypes%5B4%5D=5"
    "&paperTypes%5B5%5D=6&paperTypes%5B6%5D=7&paperTypes%5B7%5D=8"
    "&paperTypes%5B8%5D=9&showTraded=false&withBestLimits=false&hEven=0&RefID=0"
)
OUT = Path("data/iran_market_live.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "application/json,application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream,text/plain,*/*",
    "Referer": "https://tsetmc.com/",
}
NS = "http://schemas.openxmlformats.org/spreadsheetml/2006/main"


def num(value):
    if value in (None, "", "-"):
        return None
    try:
        text = str(value).translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
        return float(text.replace(",", "").replace("٬", "").replace("٫", "."))
    except (TypeError, ValueError):
        return None


def col_index(ref: str) -> int:
    match = re.match(r"[A-Z]+", ref)
    if not match:
        return 0
    value = 0
    for ch in match.group(0):
        value = value * 26 + ord(ch) - 64
    return value - 1


def cell_value(cell, shared):
    kind = cell.attrib.get("t")
    if kind == "inlineStr":
        return "".join(t.text or "" for t in cell.iter(f"{{{NS}}}t"))
    value = cell.find(f"{{{NS}}}v")
    raw = value.text if value is not None else ""
    if kind == "s" and raw:
        return shared[int(raw)]
    return raw


def read_xlsx(content: bytes) -> list[list[str]]:
    with zipfile.ZipFile(BytesIO(content)) as zf:
        names = set(zf.namelist())
        if "xl/workbook.xml" not in names:
            raise RuntimeError("response is not an XLSX workbook")
        shared = []
        if "xl/sharedStrings.xml" in names:
            root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
            for si in root.findall(f"{{{NS}}}si"):
                shared.append("".join(t.text or "" for t in si.iter(f"{{{NS}}}t")))
        sheets = sorted(n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n))
        if not sheets:
            raise RuntimeError("workbook has no worksheet")
        root = ET.fromstring(zf.read(sheets[0]))
        rows = []
        for row in root.findall(f".//{{{NS}}}sheetData/{{{NS}}}row"):
            values = {}
            for cell in row.findall(f"{{{NS}}}c"):
                ref = cell.attrib.get("r", "A1")
                values[col_index(ref)] = cell_value(cell, shared)
            if values:
                rows.append([values.get(i, "") for i in range(max(values) + 1)])
        return rows


def find_header(rows):
    required = {"l18", "pc", "py"}
    for idx, row in enumerate(rows[:12]):
        normalized = {str(v).strip().lower(): i for i, v in enumerate(row) if str(v).strip()}
        if required.issubset(normalized):
            return idx, normalized
    raise RuntimeError("Full-Market Excel header does not expose l18/pc/py")


def build_item(symbol, inscode, isin, closing, last, previous, pmax, pmin, volume, heven=""):
    return {
        "instrument": {
            "lVal18AFC": symbol,
            "insCode": str(inscode or "") or None,
            "isin": str(isin or "") or None,
        },
        "instrument_info": {
            "pClosing": closing if closing is not None else last,
            "pDrCotVal": last,
            "priceYesterday": previous,
            "priceMax": pmax,
            "priceMin": pmin,
            "qTotTran5J": volume,
            "hEven": heven,
            "quoteStatus": "ACTIVE" if volume not in (None, 0) else "SUSPENDED_OR_NO_TRADE",
        },
        "daily": [],
        "client_type_history": [],
        "major_shareholders": [],
        "codal_filings": [],
        "statement_content": [],
        "share_changes": [],
    }


def parse_excel(content: bytes):
    rows = read_xlsx(content)
    header_idx, header = find_header(rows)

    def get(row, name):
        idx = header.get(name)
        return row[idx] if idx is not None and idx < len(row) else ""

    symbols = {}
    for row in rows[header_idx + 1:]:
        symbol = str(get(row, "l18")).strip()
        if not symbol or symbol in {"نماد", "l18"}:
            continue
        price = num(get(row, "pc"))
        last = num(get(row, "pl")) or price
        previous = num(get(row, "py"))
        if price is None and last is None:
            continue
        symbols[symbol] = build_item(symbol, get(row, "inscode"), get(row, "iid"), price, last, previous, num(get(row, "pmax")), num(get(row, "pmin")), num(get(row, "tvol")), get(row, "heven"))
    return symbols


def parse_legacy_text(content: bytes):
    text = content.decode("utf-8-sig", errors="replace")
    parts = text.split("@")
    if len(parts) < 3:
        raise RuntimeError("legacy MarketWatch response has no instrument section")
    symbols = {}
    for raw in parts[2].split(";"):
        fields = raw.split(",")
        if len(fields) < 14:
            continue
        symbol = fields[2].strip()
        if not symbol or symbol in symbols:
            continue
        closing = num(fields[6])
        last = num(fields[7]) or closing
        previous = num(fields[13])
        if closing is None and last is None:
            continue
        symbols[symbol] = build_item(symbol, fields[0], None, closing, last, previous, num(fields[12]), num(fields[11]), num(fields[9]), fields[0])
    return symbols


def _first(record, *names):
    for name in names:
        value = record.get(name)
        if value not in (None, "", "-"):
            return value
    return None


def parse_cdn_marketwatch(content: bytes):
    payload = json.loads(content.decode("utf-8-sig"))
    rows = payload.get("marketwatch") if isinstance(payload, dict) else None
    if rows is None and isinstance(payload, dict):
        for value in payload.values():
            if isinstance(value, list):
                rows = value
                break
    if not isinstance(rows, list):
        raise RuntimeError("CDN MarketWatch response has no marketwatch array")

    symbols = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        symbol = str(_first(row, "lVal18AFC", "lVal18AfC", "symbol", "instrumentName") or "").strip()
        if not symbol:
            continue
        closing = num(_first(row, "pClosing", "closingPrice", "closingprice"))
        last = num(_first(row, "pDrCotVal", "lastPrice", "lastprice")) or closing
        previous = num(_first(row, "priceYesterday", "yesterdayPrice", "py"))
        if closing is None and last is None:
            continue
        symbols[symbol] = build_item(
            symbol,
            _first(row, "insCode", "inscode", "instrumentId"),
            _first(row, "isin", "ISIN"),
            closing,
            last,
            previous,
            num(_first(row, "priceMax", "pMax")),
            num(_first(row, "priceMin", "pMin")),
            num(_first(row, "qTotTran5J", "tradeVolume", "volume")),
            _first(row, "hEven", "heven") or "",
        )
    return symbols


def fetch_full_market():
    errors = []
    session = requests.Session()
    session.headers.update(HEADERS)

    # Fast path first: CDN is the preferred source for GitHub-hosted execution.
    try:
        response = session.get(CDN_MARKETWATCH_URL, timeout=(5, 12), allow_redirects=True)
        response.raise_for_status()
        symbols = parse_cdn_marketwatch(response.content)
        if len(symbols) >= 100:
            return symbols, f"tsetmc-cdn-marketwatch:{CDN_MARKETWATCH_URL}"
        errors.append(f"{CDN_MARKETWATCH_URL}: only {len(symbols)} symbols")
    except Exception as exc:
        errors.append(f"{CDN_MARKETWATCH_URL}: {type(exc).__name__}: {exc}")

    # Legacy XLSX sources are retained as secondary fallbacks.
    for url in EXCEL_URLS:
        try:
            response = session.get(url, timeout=(4, 10), allow_redirects=True)
            response.raise_for_status()
            symbols = parse_excel(response.content)
            if len(symbols) >= 100:
                return symbols, f"tsetmc-full-market-excel:{url}"
            errors.append(f"{url}: only {len(symbols)} symbols")
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")

    for url in TEXT_URLS:
        try:
            response = session.get(url, timeout=(4, 10), allow_redirects=True)
            response.raise_for_status()
            symbols = parse_legacy_text(response.content)
            if len(symbols) >= 100:
                return symbols, f"tsetmc-full-market-text:{url}"
            errors.append(f"{url}: only {len(symbols)} symbols")
        except Exception as exc:
            errors.append(f"{url}: {type(exc).__name__}: {exc}")

    raise RuntimeError("All Full-Market sources failed or returned too few symbols: " + " | ".join(errors))


def main():
    symbols, source = fetch_full_market()
    if len(symbols) < 100:
        raise RuntimeError(f"Full-Market returned only {len(symbols)} valid symbols")

    now_tehran = datetime.now(ZoneInfo("Asia/Tehran"))
    is_weekday = now_tehran.weekday() in {5, 6, 0, 1, 2}
    market_status = "OPEN" if is_weekday and 9 <= now_tehran.hour < 13 else "CLOSED"

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": source,
        "market_status": market_status,
        "universe_mode": "FULL_MARKET",
        "universe_count": len(symbols),
        "symbols": symbols,
        "errors": {},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Full-Market mirror created: {len(symbols)} symbols")
    print(f"Generated at: {payload['generated_at']}")
    print(f"Source: {source}")
    print(f"Market status: {market_status}")


if __name__ == "__main__":
    main()
