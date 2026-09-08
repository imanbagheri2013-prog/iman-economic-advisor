from __future__ import annotations

import os
from typing import Any

from .assistant_runtime import answer, load_report
from .canslim import CanSlimInput, analyze_canslim
from .fundamentals import parse_financials
from .providers.iran_market import IranMarketProvider


def _status_payload(report: dict[str, Any]) -> dict[str, Any]:
    intelligence = report.get("intelligence") or {}; live_market = report.get("live_market_intelligence") or {}
    central_bank = report.get("central_bank") or {}; portfolio = report.get("portfolio") or {}; meta = report.get("report_meta") or {}
    return {"service": "iea-assistant", "status": report.get("status", "unknown"), "pipeline_status": report.get("pipeline_status"),
        "finished_at": report.get("finished_at"), "health_status": report.get("health_status"),
        "report": {"fresh": meta.get("fresh"), "age_seconds": meta.get("age_seconds"), "max_age_seconds": meta.get("max_age_seconds"), "path": meta.get("path")},
        "market_session": report.get("market_session"), "market_status": intelligence.get("market_status"), "market_regime": intelligence.get("regime"),
        "market_score": intelligence.get("score"), "data_quality": intelligence.get("data_quality"),
        "live_market": {"status": live_market.get("status", "NOT_CONFIGURED"), "provider": live_market.get("provider"), "requested_symbols": live_market.get("requested_symbols", []), "actionable_count": live_market.get("actionable_count", 0), "signals": live_market.get("signals", []), "errors": live_market.get("errors", [])},
        "central_bank": {"ingestion_status": central_bank.get("ingestion_status"), "indicator_count": central_bank.get("indicator_count"), "monetary_impulse": central_bank.get("monetary_impulse"), "monetary_policy_index": central_bank.get("monetary_policy_index"), "stored_observation_count": central_bank.get("stored_observation_count")},
        "portfolio": {"capital": portfolio.get("capital"), "equity": portfolio.get("equity"), "current_exposure": portfolio.get("current_exposure"), "current_risk": portfolio.get("current_risk"), "drawdown": portfolio.get("drawdown")}}


def _load_fresh_report(report_path: str) -> dict[str, Any]:
    report = load_report(report_path); meta = report.get("report_meta") or {}
    if meta.get("fresh") is not True: raise RuntimeError("IEA trusted report is stale; refresh the scheduler before requesting an answer")
    return report


def _first_number(*values: Any) -> float | None:
    for value in values:
        try:
            if value is not None: return float(value)
        except (TypeError, ValueError): pass
    return None


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
            target = Path(resolved_report_path); target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_suffix(target.suffix + ".tmp"); temp.write_text(json.dumps(payload, default=str, ensure_ascii=False, indent=2), encoding="utf-8"); temp.replace(target)
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
        """Professional stock review: market, flows, holders, Codal statements and CAN SLIM."""
        try:
            data = IranMarketProvider().research_data(symbol, days=23)
            instrument = data.get("instrument_info") or {}; one = data.get("one_month") or {}; flow = data.get("money_flow") or {}
            holder = data.get("major_shareholder_change") or {}; daily = data.get("daily") or []; current = daily[0] if daily else {}
            price = _first_number(current.get("pClosing"), current.get("pDrCotVal")); high = _first_number(current.get("priceMax")); low = _first_number(current.get("priceMin"))
            near_high = None if price is None or high is None or low is None or high <= low else price >= low + .8 * (high - low)
            statement_content = data.get("statement_content") or []
            statement_source = "tsetmc_statement_content" if statement_content else "codal_metadata_fallback"
            fundamentals = parse_financials(statement_content or data.get("codal_filings") or [])
            ratios = fundamentals["ratios"]; values = fundamentals["values"]; growth = fundamentals["growth"]
            analysis = analyze_canslim(symbol=data["symbol"], data=CanSlimInput(
                price_near_high=near_high, one_month_return_pct=one.get("return_pct"), one_month_high=one.get("high"), one_month_low=one.get("low"),
                one_month_avg_volume=one.get("avg_volume"), volume_trend_pct=one.get("volume_trend_pct"), net_real_money=flow.get("real_net_value"), net_legal_money=flow.get("legal_net_value"),
                major_shareholder_change_pct=_first_number(holder.get("entries", [{}])[0].get("change") if holder.get("entries") else None),
                pe=_first_number(instrument.get("pe"), instrument.get("pE")), pb=_first_number(instrument.get("pb"), instrument.get("pB")),
                ps=_first_number(instrument.get("ps"), instrument.get("pS")), market_cap=_first_number(instrument.get("marketValue"), instrument.get("marketCap")),
                sector_pe=_first_number(instrument.get("sectorPE"), instrument.get("sectorPe")), revenue_growth_pct=growth["revenue_growth_pct"],
                gross_margin_pct=ratios["gross_margin_pct"], operating_margin_pct=ratios["operating_margin_pct"], net_margin_pct=ratios["net_margin_pct"],
                free_cash_flow=ratios["free_cash_flow"], operating_cash_flow=values["operating_cash_flow"], debt_to_equity=ratios["debt_to_equity"],
                current_ratio=ratios["current_ratio"], roe_pct=ratios["roe_pct"], roic_pct=ratios["roic_pct"], asset_growth_pct=growth["asset_growth_pct"],
                current_eps_growth_pct=growth["eps_growth_pct"], annual_eps_growth_pct=growth["annual_eps_growth_pct"]))
            analysis["market_data"] = {"provider": "tsetmc", "data_date": data.get("data_date"), "price": price, "market_status": "CLOSED"}
            analysis["one_month_behavior"] = data.get("one_month"); analysis["money_flow"] = flow
            analysis["major_shareholders"] = data.get("major_shareholders"); analysis["major_shareholder_change"] = holder
            analysis["capital_and_share_changes"] = data.get("share_changes")
            analysis["codal_filings"] = {"count": len(data.get("codal_filings") or []), "items": data.get("codal_filings") or [], "statement_parser": fundamentals["status"]}
            analysis["financial_statements"] = fundamentals
            analysis["financial_statement_source"] = statement_source
            analysis["data_quality"] = {"tsetmc_market": True, "one_month_history": bool(data.get("daily")), "money_flow_history": bool(data.get("client_type_history")),
                "major_shareholders": bool(data.get("major_shareholders")), "codal_metadata": bool(data.get("codal_filings")),
                "statement_content": bool(statement_content), "fundamental_statement_values": fundamentals["status"] == "READY", "multi_period_fundamentals": len(fundamentals.get("periods") or []) >= 2,
                "annual_fundamentals": bool(fundamentals["growth"].get("annual_eps_growth_pct") is not None or fundamentals["growth"].get("annual_revenue_growth_pct") is not None)}
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
