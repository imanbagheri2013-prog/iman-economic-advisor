from __future__ import annotations

from typing import Any

from .assistant_runtime import answer


def create_app(report_path: str = "health_report.json") -> Any:
    """Create the optional HTTP API for the IEA assistant runtime."""
    try:
        from fastapi import FastAPI
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("FastAPI is required for the IEA API") from exc

    app = FastAPI(title="IEA Assistant API", version="1.0.0")

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "iea-assistant"}

    @app.get("/answer")
    def get_answer(question: str) -> dict[str, Any]:
        return answer(question, report_path)

    return app


app = create_app()
