from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class CanSlimInput:
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
    ev_ebitda: float | None = None
    ev_sales: float | None = None
    dividend_yield_pct: float | None = None
    market_cap: float | None = None
    enterprise_value: float | None = None
    sector_pe: float | None = None
    sector_pb: float | None = None
    sector_ps: float | None = None
    sector_ev_ebitda: float | None = None
    sector_ev_sales: float | None = None
    historical_pe_percentile: float | None = None
    one_month_return_pct: float | None = None
    one_month_high: float | None = None
    one_month_low: float | None = None
    one_month_avg_volume: float | None = None
    volume_trend_pct: float | None = None
    net_real_money: float | None = None
    net_legal_money: float | None = None
    major_shareholder_change_pct: float | None = None
    market_benchmark_return_pct: float | None = None
    sector_benchmark_return_pct: float | None = None

def _metric(value: Any, reason: str, passed: bool | None = None) -> dict[str, Any]:
    return {"value": value, "pass": passed, "reason": reason}

def _weighted_score(items: list[tuple[float | None, float]]) -> tuple[float | None, float]:
    available = [(v, w) for v, w in items if v is not None]
    if not available: return None, 0.0
    total = sum(w for _, w in available)
    score = sum(float(v) * w for v, w in available) / total
    return round(score, 2), round(total / sum(w for _, w in items) * 100.0, 2)

def _relative(value: float | None, peer: float | None) -> dict[str, Any]:
    if value is None or peer is None or peer <= 0:
        return {"ratio": None, "discount_pct": None, "status": "unavailable"}
    ratio = value / peer
    return {"ratio": round(ratio, 4), "discount_pct": round((1 - ratio) * 100, 2), "status": "discount" if ratio < 1 else ("premium" if ratio > 1 else "inline")}

def _valuation_diagnostics(data: CanSlimInput) -> dict[str, Any]:
    relative = {"pe": _relative(data.pe, data.sector_pe), "pb": _relative(data.pb, data.sector_pb), "ps": _relative(data.ps, data.sector_ps), "ev_ebitda": _relative(data.ev_ebitda, data.sector_ev_ebitda), "ev_sales": _relative(data.ev_sales, data.sector_ev_sales)}
    flags: list[str] = []
    if data.pe is not None and data.pe <= 0: flags.append("non_positive_pe")
    for name, item in relative.items():
        if item["status"] == "unavailable": flags.append(f"{name}_sector_comparison_unavailable")
        elif item["ratio"] <= 0.8: flags.append(f"{name}_discount_to_sector")
        elif item["ratio"] >= 1.2: flags.append(f"{name}_premium_to_sector")
    hist = data.historical_pe_percentile
    hist_status = "unavailable" if hist is None else ("lower_than_history" if hist < 30 else ("higher_than_history" if hist > 70 else "mid_range"))
    return {"pe_vs_sector": relative["pe"]["ratio"], "pe_discount_pct": relative["pe"]["discount_pct"], "relative": relative, "forward_pe": data.forward_pe, "dividend_yield_pct": data.dividend_yield_pct, "historical_pe_percentile": hist, "historical_pe_status": hist_status, "flags": flags}

def analyze_canslim(symbol: str, data: CanSlimInput) -> dict[str, Any]:
    criteria: dict[str, dict[str, Any]] = {}
    def criterion(name: str, value: bool | None, reason: str) -> None: criteria[name] = {"pass": value, "reason": reason}
    c = None if data.current_eps_growth_pct is None else data.current_eps_growth_pct >= 20
    a = None if data.annual_eps_growth_pct is None else data.annual_eps_growth_pct >= 20
    criterion("C", c, "current EPS growth >= 20%" if c is not None else "current EPS growth unavailable")
    criterion("A", a, "annual EPS growth >= 20%" if a is not None else "annual EPS growth unavailable")
    criterion("N", data.new_catalyst, "new catalyst confirmed" if data.new_catalyst else ("no new catalyst confirmed" if data.new_catalyst is False else "new catalyst unavailable"))
    for n, v, r in [("S", data.demand_score, "supply/demand score >= 60"), ("L", data.leader_score, "relative-strength leadership >= 60"), ("I", data.institutional_sponsorship_score, "institutional sponsorship/proxy >= 60"), ("M", data.market_trend_score, "market trend >= 60")]:
        criterion(n, None if v is None else v >= 60, r if v is not None else r.replace(" >= 60", " unavailable"))
    criterion("price_position", data.price_near_high, "price is near recent high" if data.price_near_high else ("price is not near recent high" if data.price_near_high is False else "price position unavailable"))
    quality_specs = [("revenue_growth_pct", data.revenue_growth_pct, 10, "revenue growth >= 10%"), ("gross_margin_pct", data.gross_margin_pct, 20, "gross margin >= 20%"), ("operating_margin_pct", data.operating_margin_pct, 10, "operating margin >= 10%"), ("net_margin_pct", data.net_margin_pct, 8, "net margin >= 8%"), ("roe_pct", data.roe_pct, 15, "ROE >= 15%"), ("roic_pct", data.roic_pct, 10, "ROIC >= 10%"), ("current_ratio", data.current_ratio, 1.0, "current ratio >= 1.0")]
    quality = {n: _metric(v, r if v is not None else "metric unavailable", None if v is None else v >= t) for n, v, t, r in quality_specs}
    quality["debt_to_equity"] = _metric(data.debt_to_equity, "debt/equity <= 2.0" if data.debt_to_equity is not None else "metric unavailable", None if data.debt_to_equity is None else data.debt_to_equity <= 2.0)
    cash = {"free_cash_flow": _metric(data.free_cash_flow, "free cash flow positive" if data.free_cash_flow is not None else "free cash flow unavailable", None if data.free_cash_flow is None else data.free_cash_flow > 0), "operating_cash_flow": _metric(data.operating_cash_flow, "operating cash flow positive" if data.operating_cash_flow is not None else "operating cash flow unavailable", None if data.operating_cash_flow is None else data.operating_cash_flow > 0)}
    valuation = {"pe": data.pe, "forward_pe": data.forward_pe, "pb": data.pb, "ps": data.ps, "ev_ebitda": data.ev_ebitda, "ev_sales": data.ev_sales, "sector_pe": data.sector_pe, "sector_pb": data.sector_pb, "sector_ps": data.sector_ps, "sector_ev_ebitda": data.sector_ev_ebitda, "sector_ev_sales": data.sector_ev_sales, "dividend_yield_pct": data.dividend_yield_pct, "market_cap": data.market_cap, "enterprise_value": data.enterprise_value}
    diagnostics = _valuation_diagnostics(data)
    evaluated = [v for v in criteria.values() if v["pass"] is not None]
    score = round(sum(int(v["pass"]) for v in evaluated) / len(evaluated) * 100, 2) if evaluated else 0.0
    missing = [k for k, v in criteria.items() if v["pass"] is None]
    action = "CANSLIM_CANDIDATE" if score >= 85 and not missing else ("WATCH" if score >= 70 and not missing else "WAIT")
    qi = [(quality["revenue_growth_pct"]["pass"], 1.0), (quality["gross_margin_pct"]["pass"], 1.0), (quality["operating_margin_pct"]["pass"], 1.0), (quality["net_margin_pct"]["pass"], 1.0), (quality["roe_pct"]["pass"], 1.5), (quality["roic_pct"]["pass"], 1.5), (quality["current_ratio"]["pass"], .75), (quality["debt_to_equity"]["pass"], 1.0), (cash["free_cash_flow"]["pass"], 1.25), (cash["operating_cash_flow"]["pass"], 1.25)]
    qscore, coverage = _weighted_score([((100.0 if v is True else 0.0) if v is not None else None, w) for v, w in qi])
    missing_f = [n for n, m in {**quality, **cash}.items() if m["pass"] is None]
    return {"symbol": symbol, "method": "CAN SLIM + fundamental quality + valuation + flow", "score": score, "action": action, "criteria": criteria, "evaluated_criteria": len(evaluated), "missing_criteria": missing, "fundamental_quality": quality, "cash_flow_quality": cash, "valuation": valuation, "valuation_diagnostics": diagnostics, "one_month_behavior": {"one_month_return_pct": data.one_month_return_pct, "one_month_high": data.one_month_high, "one_month_low": data.one_month_low, "one_month_avg_volume": data.one_month_avg_volume, "volume_trend_pct": data.volume_trend_pct, "net_real_money": data.net_real_money, "net_legal_money": data.net_legal_money, "major_shareholder_change_pct": data.major_shareholder_change_pct}, "canslim_market_context": {"market_benchmark_return_pct": data.market_benchmark_return_pct, "sector_benchmark_return_pct": data.sector_benchmark_return_pct}, "fundamental_score": round(qscore * coverage / 100, 2) if qscore is not None else None, "fundamental_quality_score": qscore, "fundamental_score_coverage_pct": coverage, "fundamental_confidence_pct": coverage, "fundamental_score_complete": not missing_f and qscore is not None, "fundamental_missing_metrics": missing_f, "disclaimer": "Heuristic analytical framework; not an official IBD/O'Neil rating or investment guarantee."}
