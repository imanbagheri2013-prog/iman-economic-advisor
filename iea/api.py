from __future__ import annotations

import os
from typing import Any

from .assistant_runtime import answer, load_report
from .canslim import CanSlimInput, analyze_canslim
from .catalysts import detect_catalysts
from .fundamentals import parse_financials
from .providers.iran_market import IranMarketProvider


def _status_payload(report: dict[str, Any]) -> dict[str, Any]:
    intelligence = report.get("intelligence") or {}; live_market = report.get("live_market_intelligence") or {}
    central_bank = report.get("central_bank") or {}; portfolio = report.get("portfolio") or {}; meta = report.get("report_meta") or {}
    return {"service": "iea-assistant", "status": report.get("status", "unknown"), "pipeline_status": report.get("pipeline_status"), "finished_at": report.get("finished_at"), "health_status": report.get("health_status"), "report": {"fresh": meta.get("fresh"), "age_seconds": meta.get("age_seconds"), "max_age_seconds": meta.get("max_age_seconds"), "path": meta.get("path")}, "market_session": report.get("market_session"), "market_status": intelligence.get("market_status"), "market_regime": intelligence.get("regime"), "market_score": intelligence.get("score"), "data_quality": intelligence.get("data_quality"), "live_market": {"status": live_market.get("status", "NOT_CONFIGURED"), "provider": live_market.get("provider"), "requested_symbols": live_market.get("requested_symbols", []), "actionable_count": live_market.get("actionable_count", 0), "signals": live_market.get("signals", []), "errors": live_market.get("errors", [])}, "central_bank": {"ingestion_status": central_bank.get("ingestion_status"), "indicator_count": central_bank.get("indicator_count"), "monetary_impulse": central_bank.get("monetary_impulse"), "monetary_policy_index": central_bank.get("monetary_policy_index"), "stored_observation_count": central_bank.get("stored_observation_count")}, "portfolio": {"capital": portfolio.get("capital"), "equity": portfolio.get("equity"), "current_exposure": portfolio.get("current_exposure"), "current_risk": portfolio.get("current_risk"), "drawdown": portfolio.get("drawdown")}}


def _load_fresh_report(report_path: str) -> dict[str, Any]:
    report = load_report(report_path); meta = report.get("report_meta") or {}
    if meta.get("fresh") is not True: raise ValueError("IEA trusted report is stale")
    return report


def _first_number(*values: Any) -> float | None:
    for value in values:
        if value is None or value == "": continue
        try: return float(str(value).replace(",", ""))
        except (TypeError, ValueError): continue
    return None


def _clip(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _signed_flow_score(flow: dict[str, Any], prefix: str) -> float | None:
    """Return a directional flow score without inventing unavailable buy/sell totals."""
    net = _first_number(flow.get(f"{prefix}_net_value"))
    if net is None: net = _first_number(flow.get(f"{prefix}_net_volume"))
    if net is None: return None
    return 50.0 if net == 0 else (75.0 if net > 0 else 25.0)


def _canslim_market_scores(one: dict[str, Any], flow: dict[str, Any], holder: dict[str, Any], market_return: float | None, sector_return: float | None) -> dict[str, Any]:
    """Build transparent CAN SLIM S/L/I/M scores from observed data only."""
    volume_trend = _first_number(one.get("volume_trend_pct")); real_score = _signed_flow_score(flow, "real"); legal_score = _signed_flow_score(flow, "legal")
    holder_change = _first_number(holder.get("entries", [{}])[0].get("change") if holder.get("entries") else None)
    s_parts = []
    if volume_trend is not None: s_parts.append(_clip(50.0 + volume_trend * 0.30))
    if real_score is not None: s_parts.append(real_score)
    s = round(sum(s_parts) / len(s_parts), 2) if s_parts else None
    relative_returns = [r for r in (market_return, sector_return) if r is not None]
    if relative_returns:
        stock_return = _first_number(one.get("return_pct")); excess = sum(stock_return - r for r in relative_returns) / len(relative_returns) if stock_return is not None else None
        l = _clip(50.0 + excess * 5.0) if excess is not None else None
    else: l = None
    i_parts = [legal_score] if legal_score is not None else []
    if holder_change is not None: i_parts.append(_clip(50.0 + max(-50.0, min(50.0, holder_change)) * 0.5))
    i = round(sum(i_parts) / len(i_parts), 2) if i_parts else None
    m = _clip(50.0 + market_return * 5.0) if market_return is not None else None
    return {"S": s, "L": l, "I": i, "M": m, "inputs": {"volume_trend_pct": volume_trend, "real_flow_score": real_score, "legal_flow_score": legal_score, "major_shareholder_change": holder_change, "stock_return_pct": one.get("return_pct"), "market_benchmark_return_pct": market_return, "sector_benchmark_return_pct": sector_return}, "proxy_notes": {"S": "volume trend + directional real-money flow", "L": "relative return versus configured market/sector benchmark", "I": "directional legal-flow and major-shareholder sponsorship proxy; not verified institutional ownership", "M": "configured market benchmark return"}}


def _flow_composite(flow: dict[str, Any]) -> float | None:
    scores = [_signed_flow_score(flow, "real"), _signed_flow_score(flow, "legal")]
    scores = [x for x in scores if x is not None]
    return round(sum(scores) / len(scores), 2) if scores else None


def _composite_score(analysis: dict[str, Any], flow: dict[str, Any]) -> dict[str, Any]:
    """Combine fundamental quality, CAN SLIM and money flow from complete observed components only."""
    fundamental = analysis.get("fundamental_quality_score")
    canslim = analysis.get("score")
    real_flow = _signed_flow_score(flow, "real")
    legal_flow = _signed_flow_score(flow, "legal")
    # Money-flow is a composite component: require both real and legal channels
    # before counting its 20% weight. A partial flow observation remains diagnostic
    # but must not inflate composite coverage.
    money_flow = _flow_composite(flow) if real_flow is not None and legal_flow is not None else None
    components = [("fundamental", fundamental, 0.50), ("canslim", canslim, 0.30), ("money_flow", money_flow, 0.20)]
    available = [(v, w) for _, v, w in components if v is not None]
    missing = [name for name, v, _ in components if v is None]
    if not available:
        return {"score": None, "coverage_pct": 0.0, "complete": False, "missing_components": missing, "weights": {"fundamental": 0.50, "canslim": 0.30, "money_flow": 0.20}, "method": "weighted observed components; unavailable inputs excluded, never imputed"}
    total_w = sum(w for _, w in available); score = sum(float(v) * w for v, w in available) / total_w
    return {"score": round(score, 2), "coverage_pct": round(total_w * 100, 2), "complete": not missing, "missing_components": missing, "weights": {"fundamental": 0.50, "canslim": 0.30, "money_flow": 0.20}, "method": "weighted observed components; unavailable inputs excluded, never imputed"}


def create_app(report_path: str | None = None) -> Any:
    resolved_report_path = report_path or os.getenv("IEA_REPORT_PATH", "health_report.json")
    try:
        from fastapi import FastAPI, HTTPException, Header
    except ImportError as exc: raise RuntimeError("FastAPI is required for the IEA API") from exc
    app = FastAPI(title="IEA Assistant API", version="1.8.1")
    @app.get("/health")
    def health() -> dict[str, str]: return {"status": "ok", "service": "iea-assistant"}
    @app.post("/internal/report")
    def ingest_report(payload: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
        expected = os.getenv("IEA_REPORT_SINK_TOKEN")
        if not expected: raise HTTPException(status_code=503, detail="Report ingestion is not configured")
        if authorization != f"Bearer {expected}": raise HTTPException(status_code=401, detail="Unauthorized")
        if not isinstance(payload, dict) or not payload.get("finished_at"): raise HTTPException(status_code=400, detail="Invalid trusted report")
        try:
            from pathlib import Path
            import json
            target = Path(resolved_report_path); target.parent.mkdir(parents=True, exist_ok=True); temp = target.with_suffix(target.suffix + ".tmp")
            temp.write_text(json.dumps(payload, default=str, ensure_ascii=False, indent=2), encoding="utf-8"); temp.replace(target)
        except OSError as exc: raise HTTPException(status_code=500, detail=f"Unable to persist trusted report: {exc}") from exc
        return {"status": "accepted", "finished_at": payload["finished_at"]}
    @app.get("/ready")
    def ready() -> dict[str, Any]:
        try: report = load_report(resolved_report_path)
        except (RuntimeError, ValueError) as exc: raise HTTPException(status_code=503, detail=str(exc)) from exc
        meta = report.get("report_meta") or {}
        if meta.get("fresh") is not True: raise HTTPException(status_code=503, detail="IEA trusted report is stale")
        return {"status": "ready", "report": meta}
    @app.get("/status")
    def status() -> dict[str, Any]: return _status_payload(load_report(resolved_report_path))
    @app.get("/stock/canslim")
    def stock_canslim(symbol: str) -> dict[str, Any]:
        """Professional stock review: market, flows, holders, Codal statements, catalysts and CAN SLIM."""
        try:
            provider = IranMarketProvider(); data = provider.research_data(symbol, days=23)
            instrument = data.get("instrument_info") or {}; one = data.get("one_month") or {}; flow = data.get("money_flow") or {}; holder = data.get("major_shareholder_change") or {}; daily = data.get("daily") or []; current = daily[0] if daily else {}
            price = _first_number(current.get("pClosing"), current.get("pDrCotVal")); high = _first_number(current.get("priceMax")); low = _first_number(current.get("priceMin"))
            near_high = None if price is None or high is None or low is None or high <= low else price >= low + .8 * (high - low)
            statement_content = data.get("statement_content") or []; statement_source = "tsetmc_statement_content" if statement_content else "codal_metadata_fallback"
            fundamentals = parse_financials(statement_content or data.get("codal_filings") or []); ratios = fundamentals["ratios"]; values = fundamentals["values"]; growth = fundamentals["growth"]
            catalysts = detect_catalysts(data.get("codal_filings") or [])
            market_benchmark_symbol = os.getenv("IEA_IR_MARKET_INDEX_SYMBOL", "").strip(); sector_benchmark_symbol = os.getenv("IEA_IR_SECTOR_BENCHMARK_SYMBOL", "").strip()
            market_return = provider._daily_return(market_benchmark_symbol) if market_benchmark_symbol and market_benchmark_symbol != symbol else None; sector_return = provider._daily_return(sector_benchmark_symbol) if sector_benchmark_symbol and sector_benchmark_symbol != symbol else None
            market_scores = _canslim_market_scores(one, flow, holder, market_return, sector_return)
            analysis = analyze_canslim(symbol=data["symbol"], data=CanSlimInput(
                new_catalyst=catalysts["new_catalyst"], price_near_high=near_high, demand_score=market_scores["S"], leader_score=market_scores["L"], institutional_sponsorship_score=market_scores["I"], market_trend_score=market_scores["M"], market_benchmark_return_pct=market_return, sector_benchmark_return_pct=sector_return,
                one_month_return_pct=one.get("return_pct"), one_month_high=one.get("high"), one_month_low=one.get("low"), one_month_avg_volume=one.get("avg_volume"), volume_trend_pct=one.get("volume_trend_pct"), net_real_money=flow.get("real_net_value"), net_legal_money=flow.get("legal_net_value"), major_shareholder_change_pct=_first_number(holder.get("entries", [{}])[0].get("change") if holder.get("entries") else None),
                pe=_first_number(instrument.get("pe"), instrument.get("pE")), forward_pe=_first_number(instrument.get("forwardPE"), instrument.get("forwardPe")), pb=_first_number(instrument.get("pb"), instrument.get("pB")), ps=_first_number(instrument.get("ps"), instrument.get("pS")), ev_ebitda=_first_number(instrument.get("evEbitda"), instrument.get("evEBITDA")), ev_sales=_first_number(instrument.get("evSales")), market_cap=_first_number(instrument.get("marketValue"), instrument.get("marketCap")), enterprise_value=_first_number(instrument.get("enterpriseValue")), sector_pe=_first_number(instrument.get("sectorPE"), instrument.get("sectorPe")), sector_pb=_first_number(instrument.get("sectorPB"), instrument.get("sectorPb")), sector_ps=_first_number(instrument.get("sectorPS"), instrument.get("sectorPs")), sector_ev_ebitda=_first_number(instrument.get("sectorEVEBITDA"), instrument.get("sectorEvEbitda")), sector_ev_sales=_first_number(instrument.get("sectorEVSales")), dividend_yield_pct=_first_number(instrument.get("dividendYield"), instrument.get("dividendYieldPct")),
                revenue_growth_pct=growth["revenue_growth_pct"], gross_margin_pct=ratios["gross_margin_pct"], operating_margin_pct=ratios["operating_margin_pct"], net_margin_pct=ratios["net_margin_pct"], free_cash_flow=ratios["free_cash_flow"], operating_cash_flow=values["operating_cash_flow"], debt_to_equity=ratios["debt_to_equity"], current_ratio=ratios["current_ratio"], roe_pct=ratios["roe_pct"], roic_pct=ratios["roic_pct"], asset_growth_pct=growth["asset_growth_pct"], current_eps_growth_pct=growth["eps_growth_pct"], annual_eps_growth_pct=growth["annual_eps_growth_pct"]))
            analysis["market_data"] = {"provider": "tsetmc", "data_date": data.get("data_date"), "price": price, "market_status": "CLOSED"}
            analysis["canslim_market_context"] = market_scores; analysis["benchmark_configuration"] = {"market_index_symbol_configured": bool(market_benchmark_symbol), "sector_benchmark_symbol_configured": bool(sector_benchmark_symbol)}
            analysis["catalyst_diagnostics"] = catalysts
            analysis["one_month_behavior"] = data.get("one_month"); analysis["money_flow"] = flow; analysis["major_shareholders"] = data.get("major_shareholders"); analysis["major_shareholder_change"] = holder; analysis["capital_and_share_changes"] = data.get("share_changes")
            analysis["codal_filings"] = {"count": len(data.get("codal_filings") or []), "items": data.get("codal_filings") or [], "statement_parser": fundamentals["status"]}; analysis["financial_statements"] = fundamentals; analysis["financial_statement_source"] = statement_source
            analysis["composite_score"] = _composite_score(analysis, flow)
            analysis["data_quality"] = {"tsetmc_market": True, "one_month_history": bool(data.get("daily")), "money_flow_history": bool(data.get("client_type_history")), "major_shareholders": bool(data.get("major_shareholders")), "codal_metadata": bool(data.get("codal_filings")), "statement_content": bool(statement_content), "fundamental_statement_values": fundamentals["status"] == "READY", "multi_period_fundamentals": len(fundamentals.get("periods") or []) >= 2, "annual_fundamentals": bool(fundamentals["growth"].get("annual_eps_growth_pct") is not None or fundamentals["growth"].get("annual_revenue_growth_pct") is not None), "canslim_S": market_scores["S"] is not None, "canslim_L": market_scores["L"] is not None, "canslim_I": market_scores["I"] is not None, "canslim_M": market_scores["M"] is not None, "canslim_N": catalysts["new_catalyst"] is not None}
            return analysis
        except (RuntimeError, ValueError, OSError, KeyError) as exc: raise HTTPException(status_code=502, detail=str(exc)) from exc
    @app.get("/answer")
    def get_answer(question: str) -> dict[str, Any]:
        try: _load_fresh_report(resolved_report_path)
        except (RuntimeError, ValueError) as exc: raise HTTPException(status_code=503, detail=str(exc)) from exc
        return answer(question, resolved_report_path)
    return app

app = create_app()


def main() -> int:
    try: import uvicorn
    except ImportError as exc: raise RuntimeError("Uvicorn is required for the IEA API") from exc
    uvicorn.run("iea.api:app", host=os.getenv("IEA_API_HOST", "0.0.0.0"), port=int(os.getenv("PORT", os.getenv("IEA_API_PORT", "8000"))))
    return 0


if __name__ == "__main__": raise SystemExit(main())