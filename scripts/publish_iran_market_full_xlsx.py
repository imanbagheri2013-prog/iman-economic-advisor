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

URL = "https://old.tsetmc.com/tsev2/excel/MarketWatchPlus.aspx?d=0"
OUT = Path("data/iran_market_live.json")
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126 Safari/537.36",
    "Accept": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet,application/octet-stream,*/*",
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
    letters = re.match(r"[A-Z]+", ref).group(0)
    value = 0
    for ch in letters:
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
        sheet = next((n for n in names if re.fullmatch(r"xl/worksheets/sheet\d+\.xml", n)), None)
        if not sheet:
            raise RuntimeError("workbook has no worksheet")
        root = ET.fromstring(zf.read(sheet))
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
    for idx, row in enumerate(rows[:8]):
        normalized = {str(v).strip().lower(): i for i, v in enumerate(row) if str(v).strip()}
        if required.issubset(normalized):
            return idx, normalized
    raise RuntimeError("legacy Full-Market Excel header does not expose l18/pc/py")


def main():
    response = requests.get(URL, headers=HEADERS, timeout=(20, 60))
    response.raise_for_status()
    rows = read_xlsx(response.content)
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
        symbols[symbol] = {
            "instrument": {"lVal18AFC": symbol, "insCode": str(get(row, "inscode") or "") or None, "isin": str(get(row, "iid") or "") or None},
            "instrument_info": {
                "pClosing": price if price is not None else last,
                "pDrCotVal": last,
                "priceYesterday": previous,
                "priceMax": num(get(row, "pmax")),
                "priceMin": num(get(row, "pmin")),
                "qTotTran5J": num(get(row, "tvol")),
                "hEven": get(row, "heven"),
                "quoteStatus": "ACTIVE" if num(get(row, "tvol")) not in (None, 0) else "SUSPENDED_OR_NO_TRADE",
            },
            "daily": [],
            "client_type_history": [],
            "major_shareholders": [],
            "codal_filings": [],
            "statement_content": [],
            "share_changes": [],
        }

    if len(symbols) < 100:
        raise RuntimeError(f"Full-Market Excel returned only {len(symbols)} valid symbols")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "source": "tsetmc-legacy-excel:github-actions",
        "market_status": "OPEN" if datetime.now(ZoneInfo("Asia/Tehran")).weekday() in {5, 6, 0, 1, 2} else "CLOSED",
        "universe_mode": "FULL_MARKET",
        "universe_count": len(symbols),
        "symbols": symbols,
        "errors": {},
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"Full-Market Excel mirror created: {len(symbols)} symbols")
    print(f"Generated at: {payload['generated_at']}")


if __name__ == "__main__":
    main()
