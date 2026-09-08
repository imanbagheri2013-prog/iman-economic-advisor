from __future__ import annotations

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


def _norm(value: Any) -> str:
    return " ".join(str(value or "").replace("ي", "ی").replace("ك", "ک").strip().lower().split())


def _number(value: Any) -> float | None:
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    text = str(value).replace(",", "").replace("٬", "").replace(" ", "")
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


def _growth(current: float | None, previous: float | None) -> float | None:
    if current is None or previous in (None, 0):
        return None
    return (current / previous - 1.0) * 100.0


def parse_financials(payload: Any) -> dict[str, Any]:
    """Extract verified statement-line values from varied Codal payload shapes.

    This parser is deliberately conservative: absent or ambiguous values remain None.
    """
    values = {name: _find(payload, aliases) for name, aliases in ALIASES.items()}
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
            "roic_pct": None if operating is None or assets in (None, 0) else operating / assets * 100,
            "free_cash_flow": fcf,
        },
        "growth": {
            "revenue_growth_pct": None,
            "eps_growth_pct": None,
            "net_income_growth_pct": None,
        },
        "quality_flags": {
            "positive_operating_cash_flow": None if ocf is None else ocf > 0,
            "positive_free_cash_flow": None if fcf is None else fcf > 0,
        },
        "policy": "Only unambiguous statement-line values are used; missing or ambiguous values stay None.",
    }
