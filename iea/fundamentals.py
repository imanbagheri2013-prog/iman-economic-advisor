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
    "total_debt": ("total debt", "total_debt", "debt", "borrowings", "بدهی مالی", "جمع بدهی های مالی", "تسهیلات مالی"),
    "cash": ("cash", "cash and cash equivalents", "cash equivalents", "وجه نقد", "موجودی نقد", "وجه نقد و معادل نقد"),
    "tax_expense": ("tax_expense", "tax expense", "income tax", "tax", "مالیات بر درآمد", "هزینه مالیات بر درآمد"),
    "operating_cash_flow": ("operating_cash_flow", "cash from operations", "operating cash", "جریان نقد عملیاتی", "خالص جریان های نقدی حاصل از فعالیت های عملیاتی"),
    "capex": ("capex", "capital expenditure", "capital expenditures", "خرید دارایی ثابت", "مخارج سرمایه ای"),
    "dividend": ("dividend", "dividend per share", "سود تقسیمی", "سود نقدی هر سهم"),
}

_PERIOD_KEYS = ("period", "period_name", "periodName", "fiscal_year", "fiscalYear", "report_date", "reportDate", "period_end", "periodEnd", "date", "dEven", "year", "سال مالی", "دوره", "تاریخ گزارش")


def _norm(value: Any) -> str:
    return " ".join(str(value or "").replace("ي", "ی").replace("ك", "ک").strip().lower().split())


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("٬", "").replace(" ", "")
    text = text.translate(str.maketrans("۰۱۲۳۴۵۶۷۸۹٠١٢٣٤٥٦٧٨٩", "01234567890123456789"))
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
    wanted = {_norm(x) for x in _PERIOD_KEYS}
    for key, value in row.items():
        if _norm(key) in wanted and value not in (None, ""):
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
    return round((current / previous - 1.0) * 100.0, 10)


def _series_growth(rows: list[dict[str, Any]], field: str) -> float | None:
    if len(rows) < 2:
        return None
    return _growth(rows[0]["values"].get(field), rows[1]["values"].get(field))


def _period_meta(label: str | None) -> tuple[int | None, int | None, str]:
    text = _norm(label)
    years = [int(x) for x in re.findall(r"\b(?:19|20)\d{2}\b", text)]
    year = max(years) if years else None
    quarter = None
    match = re.search(r"(?:q|quarter|فصل)\s*([1-4])", text)
    if match:
        quarter = int(match.group(1))
    if quarter is None:
        for marker, value in (("سه ماهه سوم", 3), ("سه ماهه دوم", 2), ("سه ماهه اول", 1), ("سه ماهه چهارم", 4), ("سه ماهه", None)):
            if marker in text:
                quarter = value
                break
    kind = "quarter" if quarter is not None else "annual" if any(x in text for x in ("annual", "12 month", "12-month", "۱۲ ماه", "سالانه", "سالیانه", "12ماهه")) else "period"
    return year, quarter, kind


def _annual_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [row for row in rows if _period_meta(row.get("period"))[2] == "annual"]


def _yoy_growth(rows: list[dict[str, Any]], field: str) -> float | None:
    latest = rows[0] if rows else None
    if latest is None:
        return None
    year, quarter, kind = _period_meta(latest.get("period"))
    if year is None or quarter is None:
        return None
    for row in rows[1:]:
        row_year, row_quarter, row_kind = _period_meta(row.get("period"))
        if row_year == year - 1 and row_quarter == quarter:
            return _growth(latest["values"].get(field), row["values"].get(field))
    return None


def _qoq_growth(rows: list[dict[str, Any]], field: str) -> float | None:
    latest = rows[0] if rows else None
    if latest is None:
        return None
    year, quarter, kind = _period_meta(latest.get("period"))
    if year is None or quarter is None:
        return None
    target_year, target_quarter = (year - 1, 4) if quarter == 1 else (year, quarter - 1)
    for row in rows[1:]:
        row_year, row_quarter, row_kind = _period_meta(row.get("period"))
        if row_year == target_year and row_quarter == target_quarter:
            return _growth(latest["values"].get(field), row["values"].get(field))
    return None


def parse_financials(payload: Any) -> dict[str, Any]:
    """Extract conservative professional financial metrics from Codal/TSETMC payloads."""
    values = {name: _find(payload, aliases) for name, aliases in ALIASES.items()}
    periods = _period_rows(payload)
    latest = periods[0]["values"] if periods else values
    for name in values:
        if latest.get(name) is not None:
            values[name] = latest[name]

    revenue, gross = values["revenue"], values["gross_profit"]
    operating, net = values["operating_profit"], values["net_income"]
    assets, liabilities, equity = values["assets"], values["liabilities"], values["equity"]
    current_assets, current_liabilities = values["current_assets"], values["current_liabilities"]
    debt, cash, tax = values["total_debt"], values["cash"], values["tax_expense"]
    ocf, capex = values["operating_cash_flow"], values["capex"]
    fcf = None if ocf is None or capex is None else ocf - abs(capex)
    annual = _annual_rows(periods)
    growth = {
        "revenue_growth_pct": _series_growth(periods, "revenue"),
        "eps_growth_pct": _series_growth(periods, "eps"),
        "net_income_growth_pct": _series_growth(periods, "net_income"),
        "asset_growth_pct": _series_growth(periods, "assets"),
        "annual_revenue_growth_pct": _series_growth(annual, "revenue"),
        "annual_eps_growth_pct": _series_growth(annual, "eps"),
        "annual_net_income_growth_pct": _series_growth(annual, "net_income"),
        "annual_asset_growth_pct": _series_growth(annual, "assets"),
        "yoy_revenue_growth_pct": _yoy_growth(rows=periods, field="revenue"),
        "yoy_eps_growth_pct": _yoy_growth(rows=periods, field="eps"),
        "yoy_net_income_growth_pct": _yoy_growth(rows=periods, field="net_income"),
        "qoq_revenue_growth_pct": _qoq_growth(rows=periods, field="revenue"),
        "qoq_eps_growth_pct": _qoq_growth(rows=periods, field="eps"),
        "qoq_net_income_growth_pct": _qoq_growth(rows=periods, field="net_income"),
    }
    ocf_to_net = None if ocf is None or net in (None, 0) else ocf / net
    fcf_margin = None if fcf is None or revenue in (None, 0) else fcf / revenue * 100
    net_debt = None if debt is None or cash is None else debt - cash
    tax_rate = None if tax is None or operating in (None, 0) else max(0.0, min(0.5, tax / operating))
    nopat = None if operating is None or tax_rate is None else operating * (1.0 - tax_rate)
    invested_capital = None if debt is None or equity is None or cash is None else debt + equity - cash
    true_roic = None if nopat is None or invested_capital in (None, 0) else nopat / invested_capital * 100

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
            "roic_pct": true_roic,
            "roic_proxy_pct": None if operating is None or assets in (None, 0) else operating / assets * 100,
            "net_debt": net_debt,
            "net_debt_to_equity": None if net_debt is None or equity in (None, 0) else net_debt / equity,
            "free_cash_flow": fcf,
            "free_cash_flow_margin_pct": fcf_margin,
            "operating_cash_flow_to_net_income": ocf_to_net,
            "tax_rate_proxy": tax_rate,
            "invested_capital": invested_capital,
        },
        "growth": growth,
        "periods": periods[:12],
        "quality_flags": {
            "positive_operating_cash_flow": None if ocf is None else ocf > 0,
            "positive_free_cash_flow": None if fcf is None else fcf > 0,
            "cash_conversion_above_1": None if ocf_to_net is None else ocf_to_net >= 1,
            "net_debt_positive": None if net_debt is None else net_debt > 0,
            "roic_available": true_roic is not None,
            "roic_is_proxy": true_roic is None,
            "fcf_requires_capex": True,
        },
        "policy": "Only unambiguous statement-line values are used. Missing inputs remain unavailable rather than being synthesized.",
    }
