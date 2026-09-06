from __future__ import annotations

import os
from typing import Any

from .assistant_runtime import answer, load_report


def _status_payload(report: dict[str, Any]) -> dict[str, Any]:
    intelligence = report.get("intelligence") or {}
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


def create_app(report_path: str = "health_report.json") -> Any:
    """Create the HTTP API backed by the scheduler's latest trusted report."""
    try:
        from fastapi import FastAPI, HTTPException
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("FastAPI is required for the IEA API") from exc

    app = FastAPI(title="IEA Assistant API", version="1.3.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "iea-assistant"}

    @app.get("/ready")
    def ready() -> dict[str, Any]:
        try:
            report = load_report(report_path)
        except (RuntimeError, ValueError) as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from exc
        meta = report.get("report_meta") or {}
        if meta.get("fresh") is not True:
            raise HTTPException(status_code=503, detail="IEA trusted report is stale")
        return {"status": "ready", "report": meta}

    @app.get("/status")
    def status() -> dict[str, Any]:
        return _status_payload(load_report(report_path))

    @app.get("/answer")
    def get_answer(question: str) -> dict[str, Any]:
        return answer(question, report_path)

    return app


app = create_app()


def main() -> int:
    try:
        import uvicorn
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("Uvicorn is required for the IEA API") from exc
    host = os.getenv("IEA_API_HOST", "0.0.0.0")
    port = int(os.getenv("IEA_API_PORT", "8000"))
    uvicorn.run("iea.api:app", host=host, port=port)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
