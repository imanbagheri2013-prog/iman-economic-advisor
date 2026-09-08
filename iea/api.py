from __future__ import annotations

import os
from typing import Any

from .assistant_runtime import answer, load_report
from .canslim import CanSlimInput, analyze_canslim
from .providers.iran_market import IranMarketProvider


def _status_payload(report: dict[str, Any]) -> dict[str, Any]:
    intelligence = report.get("intelligence") or {}
    live_market = report.get("live_market_intelligence") or {}
    central_bank = report.get("central_bank") or {}
    portfolio = report.get("portfolio") or {}
    meta = report.get("report_meta") or {}
    return {
        "service": "iea-assistant", "status": report.get("status", "unknown"),
        "pipeline_status": report.get("pipeline_status"), "finished_at": report.get("finished_at"),
        "health_status": report.get("health_status"),
        "report": {"fresh": meta.get("fresh"), "age_seconds": meta.get("age_seconds"), "max_age_seconds": meta.get("max_age_seconds"), "path": meta.get("path")},
        "market_session": report.get("market_session"), "market_status": intelligence.get("market_status"),
        "market_regime": intelligence.get("regime"), "market_score": intelligence.get("score"), "data_quality": intelligence.get("data_quality"),
        "live_market": {"status": live_market.get("status", "NOT_CONFIGURED"), "provider": live_market.get("provider"), "requested_symbols": live_market.get("requested_symbols", []), "actionable_count": live_market.get("actionable_count", 0), "signals": live_market.get("signals", []), "errors": live_market.get("errors", [])},
        "central_bank": {"ingestion_status": central_bank.get("ingestion_status"), "indicator_count": central_bank.get("indicator_count"), "monetary_impulse": central_bank.get("monetary_impulse"), "monetary_policy_index": central_bank.get("monetary_policy_index"), "stored_observation_count": central_bank.get("stored_observation_count")},
        "portfolio": {"capital": portfolio.get("capital"), "equity": portfolio.get("equity"), "current_exposure": portfolio.get("current_exposure"), "current_risk": portfolio.get("current_risk"), "drawdown": portfolio.get("drawdown")},
    }


def _load_fresh_report(report_path: str) -> dict[str, Any]:
    report = load_report(report_path)
    meta = report.get("report_meta") or {}
    if meta.get("fresh") is not True:
        raise RuntimeError("IEA trusted report is stale; refresh the scheduler before requesting an answer")
    return report


def _first_number(*values: Any) -> float | None:
    for value in values:
        try:
            if value is not None:
                return float(value)
        except (TypeError, ValueError):
            continue
    return None


def create_app(report_path: str | None = None) -> Any:
    resolved_report_path = report_path or os.getenv("IEA_REPORT_PATH", "health_report.json")
    try:
        from fastapi import FastAPI, HTTPException, Header
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("FastAPI is required for the IEA API") from exc

    app = FastAPI(title="IEA Assistant API", version="1.5.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "iea-assistant"}

    @app.post("/internal/report")
    def ingest_report(payload: dict[str, Any], authorization: str | None = Header(default=None)) -> dict[str, Any]:
        expected = os.getenv("IEA_REPORT_SINK_TOKEN")
        if not expected:
            raise HTTPException(status_code=503, detail="Report ingestion is not configured")
        if authorization != f"Bearer {expected}":
            raise HTTPException(status_code=401, detail="Unauthorized")
        if not isinstance(payload, dict) or not payload.get("finished_at"):
            raise HTTPException(status_code=400, detail="Invalid trusted report")
        try:
            from pathlib import Path
            import json
            target = Path(resolved_report_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_suffix(target.suffix + ".tmp")
            temp.write_text(json.dumps(payload, default=str, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(target)
        except OSError as exc:
            raise HTTPException(status_code=500, detail=f"Unable to persist trusted report: {exc}") from exc
        return {"status": "accepted", "finished_at": payload["finished_at"]}

    @app.get("/ready")
    def ready() -> dict[str, Any]:
        try:
            report = load_report(resolved_report_path)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        meta = report.get("report_meta") or {}
        if meta.get("fresh") is not True:
            raise HTTPException(status_code=503, detail="IEA trusted report is stale")
        return {"status": "ready", "report": meta}

    @app.get("/status")
    def status() -> dict[str, Any]:
        return _status_payload(load_report(resolved_report_path))

    @app.get("/stock/canslim")
    def stock_canslim(symbol: str) -> dict[str, Any]:
        """Full stock review: CAN SLIM, statements when available, valuation,
        one-month price/volume behavior, real/legal money flow and major-holder changes.
        Missing fundamental fields are explicit; no accounting values are guessed.
        """
        try:
            provider = IranMarketProvider()
            data = provider.research_data(symbol, days=23)
            instrument = data.get("instrument_info") or {}
            one = data.get("one_month") or {}
            flow = data.get("money_flow") or {}
            holder = data.get("major_shareholder_change") or {}
            daily = data.get("daily") or []
            current = daily[0] if daily else {}
            price = _first_number(current.get("pClosing"), current.get("pDrCotVal"))
            high = _first_number(current.get("priceMax"))
            low = _first_number(current.get("priceMin"))
            near_high = None if price is None or high is None or low is None or high <= low else price >= low + .8 * (high - low)

            # TSETMC exposes some market-watch valuation fields. Full accounting
            # ratios remain unavailable until verified Codal statement ingestion.
            analysis = analyze_canslim(symbol=data["symbol"], data=CanSlimInput(
                price_near_high=near_high,
                one_month_return_pct=one.get("return_pct"), one_month_high=one.get("high"), one_month_low=one.get("low"),
                one_month_avg_volume=one.get("avg_volume"), volume_trend_pct=one.get("volume_trend_pct"),
                net_real_money=flow.get("real_net_value"), net_legal_money=flow.get("legal_net_value"),
                major_shareholder_change_pct=_first_number(holder.get("entries", [{}])[0].get("change") if holder.get("entries") else None),
                pe=_first_number(instrument.get("pe"), instrument.get("pE")),
                pb=_first_number(instrument.get("pb"), instrument.get("pB")),
                ps=_first_number(instrument.get("ps"), instrument.get("pS")),
                market_cap=_first_number(instrument.get("marketValue"), instrument.get("marketCap")),
                sector_pe=_first_number(instrument.get("sectorPE"), instrument.get("sectorPe")),
                current_eps_growth_pct=None, annual_eps_growth_pct=None, new_catalyst=None,
                demand_score=None, leader_score=None, institutional_sponsorship_score=None, market_trend_score=None,
            ))
            analysis["market_data"] = {
                "provider": "tsetmc", "data_date": data.get("data_date"), "price": price,
                "market_status": "CLOSED" if not data.get("data_date") else "CLOSED",
            }
            analysis["one_month_behavior"] = data.get("one_month")
            analysis["money_flow"] = flow
            analysis["major_shareholders"] = data.get("major_shareholders")
            analysis["major_shareholder_change"] = holder
            analysis["financial_statements"] = {
                "status": "NOT_YET_INGESTED",
                "required": [
                    "income_statement", "balance_sheet", "cash_flow_statement", "quarterly_revenue_and_eps",
                    "operating_margin", "net_margin", "roe", "roic", "debt_to_equity", "free_cash_flow",
                    "working_capital", "receivables", "inventory", "capex", "dividend_history",
                ],
                "policy": "No fundamental value is fabricated; Codal ingestion is required before these fields affect the score.",
            }
            return analysis
        except (RuntimeError, ValueError, OSError, KeyError) as exc:
            raise HTTPException(status_code=502, detail=str(exc)) from exc

    @app.get("/answer")
    def get_answer(question: str) -> dict[str, Any]:
        try:
            _load_fresh_report(resolved_report_path)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        return answer(question, resolved_report_path)

    return app


app = create_app()


def main() -> int:
    try:
        import uvicorn
    except ImportError as exc:
        raise RuntimeError("Uvicorn is required for the IEA API") from exc
    host = os.getenv("IEA_API_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("IEA_API_PORT", "8000")))
    uvicorn.run("iea.api:app", host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
