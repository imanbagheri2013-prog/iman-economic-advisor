from __future__ import annotations

import re
from typing import Any


ALIASES: dict[str, tuple[str, ...]] = {
    "revenue": ("revenue", "sales", "revenues", "درآمد عملیاتی", "فروش"),
    "gross_profit": ("gross_profit", "grossprofit", "gross profit", "سود ناخالص", "سود ناخالص عملیاتی"),
    "operating_profit": ("operating_profit", "operatingprofit", "operating profit", "سود عملیاتی"),
    "net_income": ("net_income", "netincome", "net profit", "profit", "سود خالص", "سود(زیان) خالص"),
    "eps": ("eps", "earning per share", "eps diluted", "سود هر سهم", "eps - سود هر سهم"),
    "assets": ("assets", "total assets", "جمع دارایی ها", "جمع دارایی‌ها"),
    "liabilities": ("liabilities", "total liabilities", "جمع بدهی ها", "جمع بدهی‌ها"),
    "equity": ("equity", "shareholders equity", "total equity", "حقوق صاحبان سهام", "جمع حقوق صاحبان سهام"),
    "current_assets": ("current_assets", "current assets", "دارایی های جاری", "دارایی‌های جاری"),
    "current_liabilities": ("current_liabilities", "current liabilities", "بدهی های جاری", "بدهی‌های جاری"),
    "operating_cash_flow": ("operating_cash_flow", "cash from operations", "operating cash", "جریان نقد عملیاتی", "خالص جریان های نقدی حاصل از فعالیت های عملیاتی"),
    "capex": ("capex", "capital expenditure", "capital expenditures", "خرید دارایی ثابت", "مخارج سرمایه ای"),
    "dividend": ("dividend", "dividend per share", "سود تقسیمی", "سود نقدی هر سهم"),
}

_PERIOD_KEYS = (
    "period", "period_name", "periodName", "fiscal_year", "fiscalYear", "report_date", "reportDate",
    "period_end", "periodEnd", "date", "dEven", "year", "سال مالی", "دوره", "تاریخ گزارش",
)


def _norm(value: Any) -> str:
    return " ".join(str(value or "").replace("ي", "ی").replace("ك", "ک").strip().lower().split())


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("٬", "").replace(" ", "")
    # Persian/Arabic digits are common in Codal labels and period fields.
    text = str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789").__class__ and text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
    try:
        return float(text)
    except ValueError:
        return None


def _walk(obj: Any):
    if isinstance(obj, dict):
        yield obj
        for value in obj.values():
            yield from _walk(value)
    elif isinstance(obj, list):
        for value in obj:
            yield from _walk(value)


def _find(payload: Any, aliases: tuple[str, ...]) -> float | None:
    wanted = {_norm(x) for x in aliases}
    for item in _walk(payload):
        for key, value in item.items():
            nk = _norm(key)
            if nk in wanted:
                direct = _number(value)
                if direct is not None:
                    return direct
            if nk in {"name", "title", "label", "item", "شرح", "شرح آیتم"} and _norm(value) in wanted:
                for candidate_key in ("value", "amount", "number", "current", "current_value", "مبلغ", "مقدار"):
                    if candidate_key in item:
                        direct = _number(item[candidate_key])
                        if direct is not None:
                            return direct
    return None


def _period_label(row: dict[str, Any]) -> str | None:
    for key in _PERIOD_KEYS:
        if key in row and row[key] not in (None, ""):
            return str(row[key])
    for key, value in row.items():
        if _norm(key) in {_norm(x) for x in _PERIOD_KEYS} and value not in (None, ""):
            return str(value)
    return None


def _period_rank(label: str | None, fallback: int) -> tuple[int, int]:
    if not label:
        return (0, -fallback)
    digits = re.findall(r"\d{4,8}", label)
    if digits:
        return (1, max(int(x) for x in digits))
    return (0, -fallback)


def _period_rows(payload: Any) -> list[dict[str, Any]]:
    rows: list[tuple[tuple[int, int], dict[str, Any]]] = []
    for index, item in enumerate(_walk(payload)):
        if not isinstance(item, dict):
            continue
        values = {name: _find(item, aliases) for name, aliases in ALIASES.items()}
        if not any(value is not None for value in values.values()):
            continue
        label = _period_label(item)
        rows.append((_period_rank(label, index), {"period": label, "values": values}))
    # Most TSETMC/Codal lists are newest-first; explicit period/date values are
    # sorted newest-first while rows without a period keep their source order.
    rows.sort(key=lambda pair: pair[0], reverse=True)
    deduped: list[dict[str, Any]] = []
    seen: set[tuple[str | None, tuple[tuple[str, float | None], ...]]] = set()
    for _, row in rows:
        signature = (row["period"], tuple(sorted(row["values"].items())))
        if signature not in seen:
            seen.add(signature)
            deduped.append(row)
    return deduped


def _growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1.0) * 100.0


def _series_growth(rows: list[dict[str, Any]], field: str) -> float | None:
    if len(rows) < 2:
        return None
    return _growth(rows[0]["values"].get(field), rows[1]["values"].get(field))


def _annual_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annual_markers = ("annual", "year", "12 month", "12-month", "۱۲ ماه", "سالانه", "سالیانه", "12ماهه")
    selected = [row for row in rows if any(marker in _norm(row.get("period")) for marker in annual_markers)]
    return selected


def parse_financials(payload: Any) -> dict[str, Any]:
    """Extract conservative financial metrics from Codal/TSETMC payloads.

    The parser never fabricates a missing value. When multiple statement periods
    are present, it uses the newest two periods for sequential growth and only
    labels annual EPS growth when the source explicitly identifies annual data.
    """
    values = {name: _find(payload, aliases) for name, aliases in ALIASES.items()}
    periods = _period_rows(payload)
    latest = periods[0]["values"] if periods else values
    # Prefer the newest identified period for scalar statement values.
    for name in values:
        if latest.get(name) is not None:
            values[name] = latest[name]

    revenue = values["revenue"]
    gross = values["gross_profit"]
    operating = values["operating_profit"]
    net = values["net_income"]
    assets = values["assets"]
    liabilities = values["liabilities"]
    equity = values["equity"]
    current_assets = values["current_assets"]
    current_liabilities = values["current_liabilities"]
    ocf = values["operating_cash_flow"]
    capex = values["capex"]
    fcf = None if ocf is None else ocf - abs(capex or 0.0)
    annual = _annual_rows(periods)
    growth = {
        "revenue_growth_pct": _series_growth(periods, "revenue"),
        "eps_growth_pct": _series_growth(periods, "eps"),
        "net_income_growth_pct": _series_growth(periods, "net_income"),
        "annual_revenue_growth_pct": _series_growth(annual, "revenue"),
        "annual_eps_growth_pct": _series_growth(annual, "eps"),
        "annual_net_income_growth_pct": _series_growth(annual, "net_income"),
    }
    ocf_to_net = None if ocf is None or net in (None, 0) else ocf / net
    fcf_margin = None if fcf is None or revenue in (None, 0) else fcf / revenue * 100
    return {
        "status": "READY" if any(v is not None for v in values.values()) else "NO_STATEMENT_VALUES",
        "values": values,
        "ratios": {
            "gross_margin_pct": None if gross is None or revenue in (None, 0) else gross / revenue * 100,
            "operating_margin_pct": None if operating is None or revenue in (None, 0) else operating / revenue * 100,
            "net_margin_pct": None if net is None or revenue in (None, 0) else net / revenue * 100,
            "debt_to_equity": None if liabilities is None or equity in (None, 0) else liabilities / equity,
            "current_ratio": None if current_assets is None or current_liabilities in (None, 0) else current_assets / current_liabilities,
            "roe_pct": None if net is None or equity in (None, 0) else net / equity * 100,
            "roa_pct": None if net is None or assets in (None, 0) else net / assets * 100,
            # Conservative proxy: true ROIC needs invested capital and tax data.
            "roic_pct": None if operating is None or assets in (None, 0) else operating / assets * 100,
            "free_cash_flow": fcf,
            "free_cash_flow_margin_pct": fcf_margin,
            "operating_cash_flow_to_net_income": ocf_to_net,
        },
        "growth": growth,
        "periods": periods[:12],
        "quality_flags": {
            "positive_operating_cash_flow": None if ocf is None else ocf > 0,
            "positive_free_cash_flow": None if fcf is None else fcf > 0,
            "cash_conversion_above_1": None if ocf_to_net is None else ocf_to_net >= 1,
            "roic_is_proxy": True,
        },
        "policy": "Only unambiguous statement-line values are used; missing or ambiguous values stay None. Sequential growth requires at least two identifiable periods; annual growth requires explicit annual-period labels.",
    }
