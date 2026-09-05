from __future__ import annotations

import csv
import io
import os
from dataclasses import dataclass
from typing import Any

import requests

from .equity_fundamentals import FundamentalSnapshot

SEC_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SEC_FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik:010d}.json"
STOOQ_QUOTE_URL = "https://stooq.com/q/l/"


@dataclass(frozen=True)
class LiveEquityInput:
    snapshot: FundamentalSnapshot
    current_price: float
    method_values: tuple[float, ...]
    method_weights: tuple[float, ...]
    methods_used: tuple[str, ...]
    source: str


def _headers() -> dict[str, str]:
    user_agent = os.getenv("IEA_SEC_USER_AGENT", "IEA Economic Advisor research contact@example.com")
    return {"User-Agent": user_agent, "Accept-Encoding": "gzip, deflate"}


def _get_json(url: str, timeout: float) -> Any:
    response = requests.get(url, headers=_headers(), timeout=timeout)
    response.raise_for_status()
    return response.json()


def _sec_cik(symbol: str, timeout: float) -> int:
    payload = _get_json(SEC_TICKERS_URL, timeout)
    symbol = symbol.upper()
    for row in payload.values():
        if str(row.get("ticker", "")).upper() == symbol:
            return int(row["cik_str"])
    raise ValueError(f"SEC ticker not found: {symbol}")


def _annual_values(facts: dict[str, Any], concepts: tuple[str, ...]) -> list[float]:
    """Return annual SEC values, newest first, from the us-gaap facts map."""
    rows: list[dict[str, Any]] = []
    for concept in concepts:
        concept_data = facts.get(concept, {})
        for unit_rows in concept_data.values():
            if isinstance(unit_rows, dict) and isinstance(unit_rows.get("units"), list):
                unit_rows = unit_rows["units"]
            if isinstance(unit_rows, list):
                rows.extend(row for row in unit_rows if isinstance(row, dict))

    annual = [
        row for row in rows
        if row.get("form") in {"10-K", "10-K/A"} and row.get("val") is not None
    ]
    annual.sort(key=lambda row: (str(row.get("end", "")), str(row.get("filed", ""))), reverse=True)

    dedup: dict[str, dict[str, Any]] = {}
    for row in annual:
        end = str(row.get("end", ""))
        if end and end not in dedup:
            dedup[end] = row
    return [float(dedup[key]["val"]) for key in dedup]


def _latest(facts: dict[str, Any], concepts: tuple[str, ...], *, required: bool = True) -> float | None:
    values = _annual_values(facts, concepts)
    if not values:
        if required:
            raise ValueError(f"SEC fact unavailable: {concepts[0]}")
        return None
    return values[0]


def _prior(facts: dict[str, Any], concepts: tuple[str, ...]) -> float | None:
    values = _annual_values(facts, concepts)
    return values[1] if len(values) > 1 else None


def _stooq_price(symbol: str, timeout: float) -> float:
    stooq_symbol = symbol.lower() + ".us"
    response = requests.get(
        STOOQ_QUOTE_URL,
        params={"s": stooq_symbol, "f": "sd2t2ohlcv", "h": "", "e": "csv"},
        timeout=timeout,
    )
    response.raise_for_status()
    rows = list(csv.DictReader(io.StringIO(response.text)))
    if not rows or rows[0].get("Close") in {None, "", "N/D"}:
        raise ValueError(f"Stooq price unavailable: {symbol}")
    return float(rows[0]["Close"])


def fetch_live_equity_input(symbol: str, timeout: float = 15.0) -> LiveEquityInput:
    """Build a real US-equity advisor input from SEC filings plus Stooq price.

    No synthetic financial values are generated. If a required SEC fact or
    market price is unavailable, the call fails rather than fabricating data.
    Valuation uses a configurable peer P/E assumption, defaulting to 15.
    """
    symbol = symbol.upper().strip()
    if not symbol:
        raise ValueError("symbol must not be empty")

    cik = _sec_cik(symbol, timeout)
    company = _get_json(SEC_FACTS_URL.format(cik=cik), timeout)
    facts = company["facts"]["us-gaap"]

    revenue = _latest(facts, ("RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"))
    gross_profit = _latest(facts, ("GrossProfit",))
    operating_profit = _latest(facts, ("OperatingIncomeLoss",))
    net_profit = _latest(facts, ("NetIncomeLoss",))
    operating_cash_flow = _latest(facts, ("NetCashProvidedByUsedInOperatingActivities",))
    capex = _latest(facts, ("PaymentsToAcquirePropertyPlantAndEquipment",), required=False) or 0.0
    debt_current = _latest(facts, ("LongTermDebtCurrent",), required=False) or 0.0
    debt_noncurrent = _latest(facts, ("LongTermDebtNoncurrent",), required=False) or 0.0
    cash = _latest(facts, ("CashAndCashEquivalentsAtCarryingValue", "CashCashEquivalentsRestrictedCashAndRestrictedCashEquivalents"))
    equity = _latest(facts, ("StockholdersEquity", "StockholdersEquityIncludingPortionAttributableToNoncontrollingInterest"))
    shares = _latest(facts, ("EntityCommonStockSharesOutstanding",), required=False)
    if shares is None or shares <= 0:
        raise ValueError(f"SEC shares outstanding unavailable: {symbol}")

    prior_revenue = _prior(facts, ("RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"))
    prior_net_profit = _prior(facts, ("NetIncomeLoss",))
    price = _stooq_price(symbol, timeout)

    snapshot = FundamentalSnapshot(
        symbol=symbol,
        revenue=revenue,
        gross_profit=gross_profit,
        operating_profit=operating_profit,
        net_profit=net_profit,
        operating_cash_flow=operating_cash_flow,
        capex=capex,
        total_debt=debt_current + debt_noncurrent,
        cash=cash,
        equity=equity,
        shares_outstanding=shares,
        prior_revenue=prior_revenue,
        prior_net_profit=prior_net_profit,
    )

    pe_multiple = float(os.getenv("IEA_EQUITY_PE_MULTIPLE", "15"))
    if pe_multiple <= 0:
        raise ValueError("IEA_EQUITY_PE_MULTIPLE must be positive")
    eps = net_profit / shares
    if eps <= 0:
        raise ValueError(f"positive EPS required for PE valuation: {symbol}")
    pe_value = round(eps * pe_multiple, 10)

    return LiveEquityInput(
        snapshot=snapshot,
        current_price=price,
        method_values=(pe_value,),
        method_weights=(1.0,),
        methods_used=("pe_sec_fundamentals",),
        source="SEC_COMPANYFACTS+STOOQ",
    )
