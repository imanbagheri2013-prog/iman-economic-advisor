from __future__ import annotations

import os
from typing import Any

from .assistant_runtime import answer, load_report


def _status_payload(report: dict[str, Any]) -> dict[str, Any]:
    intelligence = report.get("intelligence") or {}
    live_market = report.get("live_market_intelligence") or {}
    central_bank = report.get("central_bank") or {}
    portfolio = report.get("portfolio") or {}
    meta = report.get("report_meta") or {}
    return {
        "service": "iea-assistant",
        "status": report.get("status", "unknown"),
        "pipeline_status": report.get("pipeline_status"),
        "finished_at": report.get("finished_at"),
        "health_status": report.get("health_status"),
        "report": {
            "fresh": meta.get("fresh"),
            "age_seconds": meta.get("age_seconds"),
            "max_age_seconds": meta.get("max_age_seconds"),
            "path": meta.get("path"),
        },
        "market_session": report.get("market_session"),
        "market_status": intelligence.get("market_status"),
        "market_regime": intelligence.get("regime"),
        "market_score": intelligence.get("score"),
        "data_quality": intelligence.get("data_quality"),
        "live_market": {
            "status": live_market.get("status", "NOT_CONFIGURED"),
            "provider": live_market.get("provider"),
            "requested_symbols": live_market.get("requested_symbols", []),
            "actionable_count": live_market.get("actionable_count", 0),
            "signals": live_market.get("signals", []),
            "errors": live_market.get("errors", []),
        },
        "central_bank": {
            "ingestion_status": central_bank.get("ingestion_status"),
            "indicator_count": central_bank.get("indicator_count"),
            "monetary_impulse": central_bank.get("monetary_impulse"),
            "monetary_policy_index": central_bank.get("monetary_policy_index"),
            "stored_observation_count": central_bank.get("stored_observation_count"),
        },
        "portfolio": {
            "capital": portfolio.get("capital"),
            "equity": portfolio.get("equity"),
            "current_exposure": portfolio.get("current_exposure"),
            "current_risk": portfolio.get("current_risk"),
            "drawdown": portfolio.get("drawdown"),
        },
    }


def _load_fresh_report(report_path: str) -> dict[str, Any]:
    """Load the trusted report and enforce the freshness boundary for decisions."""
    report = load_report(report_path)
    meta = report.get("report_meta") or {}
    if meta.get("fresh") is not True:
        raise RuntimeError("IEA trusted report is stale; refresh the scheduler before requesting an answer")
    return report


def create_app(report_path: str | None = None) -> Any:
    """Create the HTTP API backed by the scheduler's latest trusted report."""
    resolved_report_path = report_path or os.getenv("IEA_REPORT_PATH", "health_report.json")
    try:
        from fastapi import FastAPI, HTTPException, Header
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("FastAPI is required for the IEA API") from exc

    app = FastAPI(title="IEA Assistant API", version="1.3.0")

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
            target = Path(resolved_report_path)
            target.parent.mkdir(parents=True, exist_ok=True)
            temp = target.with_suffix(target.suffix + ".tmp")
            import json
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
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Uvicorn is required for the IEA API") from exc
    host = os.getenv("IEA_API_HOST", "0.0.0.0")
    port = int(os.getenv("PORT", os.getenv("IEA_API_PORT", "8000")))
    uvicorn.run("iea.api:app", host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
