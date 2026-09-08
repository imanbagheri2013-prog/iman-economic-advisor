from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CanSlimInput:
    """Inputs for a transparent, institutional-style equity review.

    None means unavailable. The engine never invents accounting or market data.
    """

    current_eps_growth_pct: float | None = None
    annual_eps_growth_pct: float | None = None
    new_catalyst: bool | None = None
    price_near_high: bool | None = None
    demand_score: float | None = None
    leader_score: float | None = None
    institutional_sponsorship_score: float | None = None
    market_trend_score: float | None = None

    revenue_growth_pct: float | None = None
    gross_margin_pct: float | None = None
    operating_margin_pct: float | None = None
    net_margin_pct: float | None = None
    free_cash_flow: float | None = None
    operating_cash_flow: float | None = None
    debt_to_equity: float | None = None
    current_ratio: float | None = None
    roe_pct: float | None = None
    roic_pct: float | None = None
    asset_growth_pct: float | None = None
    pe: float | None = None
    forward_pe: float | None = None
    pb: float | None = None
    ps: float | None = None
    dividend_yield_pct: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    sector_pe: float | None = None

    one_month_return_pct: float | None = None
    one_month_high: float | None = None
    one_month_low: float | None = None
    one_month_avg_volume: float | None = None
    volume_trend_pct: float | None = None
    net_real_money: float | None = None
    net_legal_money: float | None = None
    major_shareholder_change_pct: float | None = None


def _metric(value: Any, reason: str, passed: bool | None = None) -> dict[str, Any]:
    return {"value": value, "pass": passed, "reason": reason}


def _weighted_score(items: list[tuple[float | None, float]]) -> tuple[float | None, float]:
    available = [(value, weight) for value, weight in items if value is not None]
    if not available:
        return None, 0.0
    total_weight = sum(weight for _, weight in available)
    score = sum(float(value) * weight for value, weight in available) / total_weight
    coverage = total_weight / sum(weight for _, weight in items)
    return round(score, 2), round(coverage * 100.0, 2)


def analyze_canslim(symbol: str, data: CanSlimInput) -> dict[str, Any]:
    """Produce CAN SLIM + fundamental quality + valuation + flow diagnostics.

    Thresholds are conservative heuristics, not an official IBD/O'Neil rating.
    Missing inputs remain missing and reduce confidence rather than becoming
    synthetic positives.
    """
    criteria: dict[str, dict[str, Any]] = {}

    def criterion(name: str, value: bool | None, reason: str) -> None:
        criteria[name] = {"pass": value, "reason": reason}

    c_pass = data.current_eps_growth_pct is not None and data.current_eps_growth_pct >= 20
    criterion("C", c_pass if data.current_eps_growth_pct is not None else None,
              "current EPS growth >= 20%" if data.current_eps_growth_pct is not None else "current EPS growth unavailable")
    a_pass = data.annual_eps_growth_pct is not None and data.annual_eps_growth_pct >= 20
    criterion("A", a_pass if data.annual_eps_growth_pct is not None else None,
              "annual EPS growth >= 20%" if data.annual_eps_growth_pct is not None else "annual EPS growth unavailable")
    criterion("N", data.new_catalyst, "new catalyst confirmed" if data.new_catalyst else ("no new catalyst confirmed" if data.new_catalyst is False else "new catalyst unavailable"))
    criterion("S", None if data.demand_score is None else data.demand_score >= 60,
              "demand score >= 60" if data.demand_score is not None else "supply/demand data unavailable")
    criterion("L", None if data.leader_score is None else data.leader_score >= 60,
              "leadership/relative strength >= 60" if data.leader_score is not None else "relative-strength data unavailable")
    criterion("I", None if data.institutional_sponsorship_score is None else data.institutional_sponsorship_score >= 60,
              "institutional sponsorship >= 60" if data.institutional_sponsorship_score is not None else "institutional sponsorship data unavailable")
    criterion("M", None if data.market_trend_score is None else data.market_trend_score >= 60,
              "market trend >= 60" if data.market_trend_score is not None else "market trend data unavailable")
    criterion("price_position", data.price_near_high,
              "price is near recent high" if data.price_near_high else ("price is not near recent high" if data.price_near_high is False else "price position unavailable"))

    quality: dict[str, dict[str, Any]] = {}
    quality_specs = [
        ("revenue_growth_pct", data.revenue_growth_pct, 10, "revenue growth >= 10%"),
        ("gross_margin_pct", data.gross_margin_pct, 20, "gross margin >= 20%"),
        ("operating_margin_pct", data.operating_margin_pct, 10, "operating margin >= 10%"),
        ("net_margin_pct", data.net_margin_pct, 8, "net margin >= 8%"),
        ("roe_pct", data.roe_pct, 15, "ROE >= 15%"),
        ("roic_pct", data.roic_pct, 10, "ROIC >= 10%"),
        ("current_ratio", data.current_ratio, 1.0, "current ratio >= 1.0"),
    ]
    for name, value, threshold, reason in quality_specs:
        passed = None if value is None else value >= threshold
        quality[name] = _metric(value, reason if value is not None else "metric unavailable", passed)
    quality["debt_to_equity"] = _metric(
        data.debt_to_equity,
        "debt/equity <= 2.0" if data.debt_to_equity is not None else "metric unavailable",
        None if data.debt_to_equity is None else data.debt_to_equity <= 2.0,
    )

    cash_quality = {
        "free_cash_flow": _metric(data.free_cash_flow, "free cash flow positive" if data.free_cash_flow is not None else "free cash flow unavailable", None if data.free_cash_flow is None else data.free_cash_flow > 0),
        "operating_cash_flow": _metric(data.operating_cash_flow, "operating cash flow positive" if data.operating_cash_flow is not None else "operating cash flow unavailable", None if data.operating_cash_flow is None else data.operating_cash_flow > 0),
    }

    valuation = {
        "pe": data.pe, "forward_pe": data.forward_pe, "pb": data.pb, "ps": data.ps,
        "sector_pe": data.sector_pe, "dividend_yield_pct": data.dividend_yield_pct,
        "market_cap": data.market_cap, "enterprise_value": data.enterprise_value,
    }
    valuation_diagnostics: dict[str, Any] = {
        "pe_vs_sector": None,
        "pe_discount_pct": None,
        "flags": [],
    }
    if data.pe is not None and data.sector_pe is not None and data.sector_pe > 0:
        valuation_diagnostics["pe_vs_sector"] = round(data.pe / data.sector_pe, 4)
        valuation_diagnostics["pe_discount_pct"] = round((1 - data.pe / data.sector_pe) * 100.0, 2)
        if data.pe <= data.sector_pe * 0.8:
            valuation_diagnostics["flags"].append("pe_discount_to_sector")
        elif data.pe >= data.sector_pe * 1.2:
            valuation_diagnostics["flags"].append("pe_premium_to_sector")
    elif data.pe is None or data.sector_pe is None:
        valuation_diagnostics["flags"].append("sector_pe_comparison_unavailable")
    if data.pe is not None and data.pe <= 0:
        valuation_diagnostics["flags"].append("non_positive_pe")

    flow = {
        "one_month_return_pct": data.one_month_return_pct,
        "one_month_high": data.one_month_high,
        "one_month_low": data.one_month_low,
        "one_month_avg_volume": data.one_month_avg_volume,
        "volume_trend_pct": data.volume_trend_pct,
        "net_real_money": data.net_real_money,
        "net_legal_money": data.net_legal_money,
        "major_shareholder_change_pct": data.major_shareholder_change_pct,
    }

    evaluated = [v for v in criteria.values() if v["pass"] is not None]
    p = sum(int(v["pass"]) for v in evaluated)
    score = round(p / len(evaluated) * 100.0, 2) if evaluated else 0.0
    missing = [k for k, v in criteria.items() if v["pass"] is None]
    action = "CANSLIM_CANDIDATE" if score >= 85 and not missing else ("WATCH" if score >= 70 and not missing else "WAIT")

    quality_items = [
        (quality["revenue_growth_pct"]["pass"], 1.0),
        (quality["gross_margin_pct"]["pass"], 1.0),
        (quality["operating_margin_pct"]["pass"], 1.0),
        (quality["net_margin_pct"]["pass"], 1.0),
        (quality["roe_pct"]["pass"], 1.5),
        (quality["roic_pct"]["pass"], 1.5),
        (quality["current_ratio"]["pass"], 0.75),
        (quality["debt_to_equity"]["pass"], 1.0),
        (cash_quality["free_cash_flow"]["pass"], 1.25),
        (cash_quality["operating_cash_flow"]["pass"], 1.25),
    ]
    quality_score, quality_coverage = _weighted_score(
        [((100.0 if value is True else 0.0) if value is not None else None, weight) for value, weight in quality_items]
    )
    fundamental_score = quality_score
    fundamental_missing = [
        name for name, metric in {**quality, **cash_quality}.items() if metric["pass"] is None
    ]
    fundamental_complete = not fundamental_missing and quality_score is not None

    return {
        "symbol": symbol,
        "method": "CAN SLIM + fundamental quality + valuation + flow",
        "score": score,
        "action": action,
        "criteria": criteria,
        "evaluated_criteria": len(evaluated),
        "missing_criteria": missing,
        "fundamental_quality": quality,
        "cash_flow_quality": cash_quality,
        "valuation": valuation,
        "valuation_diagnostics": valuation_diagnostics,
        "one_month_behavior": flow,
        "fundamental_score": fundamental_score,
        "fundamental_score_coverage_pct": quality_coverage,
        "fundamental_score_complete": fundamental_complete,
        "fundamental_missing_metrics": fundamental_missing,
        "disclaimer": "Heuristic analytical framework; not an official IBD/O'Neil rating or investment guarantee.",
    }
