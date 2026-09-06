from __future__ import annotations

from typing import Any

from .assistant_runtime import answer, load_report


def _status_payload(report: dict[str, Any]) -> dict[str, Any]:
    intelligence = report.get("intelligence") or {}
    central_bank = report.get("central_bank") or {}
    portfolio = report.get("portfolio") or {}
    return {
        "status": report.get("status", "unknown"),
        "finished_at": report.get("finished_at"),
        "health_status": report.get("health_status"),
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
    """Create the optional HTTP API for the IEA assistant runtime."""
    try:
        from fastapi import FastAPI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("FastAPI is required for the IEA API") from exc

    app = FastAPI(title="IEA Assistant API", version="1.1.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "iea-assistant"}

    @app.get("/status")
    def status() -> dict[str, Any]:
        return _status_payload(load_report(report_path))

    @app.get("/answer")
    def get_answer(question: str) -> dict[str, Any]:
        return answer(question, report_path)

    return app


app = create_app()
