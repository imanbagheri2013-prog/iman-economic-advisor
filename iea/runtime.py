from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .advisor import build_equity_advisor_report
from .eight_factor import analyze_eight_factor
from .equity_fundamentals import FundamentalSnapshot


def load_equity_payload(path: str | Path) -> dict[str, Any]:
    """Load a validated-by-constructor equity input payload from JSON."""
    with Path(path).open("r", encoding="utf-8") as fh:
        payload = json.load(fh)
    if not isinstance(payload, dict):
        raise ValueError("equity payload must be a JSON object")
    required = {"snapshot", "current_price", "method_values", "method_weights"}
    missing = sorted(required - payload.keys())
    if missing:
        raise ValueError(f"missing equity payload fields: {', '.join(missing)}")
    return payload


def build_live_equity_advisor_report(
    store: Any,
    payload: dict[str, Any],
    *,
    market_adapter: Any | None = None,
    sentiment_adapter: Any | None = None,
    news_adapter: Any | None = None,
    capital: float | None = None,
) -> dict[str, Any]:
    """Run the live market pipeline and feed it into the unified equity advisor."""
    snapshot = FundamentalSnapshot(**payload["snapshot"])
    market_report = analyze_eight_factor(
        store,
        market_adapter=market_adapter,
        sentiment_adapter=sentiment_adapter,
        news_adapter=news_adapter,
        capital=capital,
    )
    return build_equity_advisor_report(
        snapshot=snapshot,
        current_price=float(payload["current_price"]),
        method_values=payload["method_values"],
        method_weights=payload["method_weights"],
        market_report=market_report,
        confidence=float(payload.get("confidence", 0.7)),
        downside=float(payload.get("downside", 0.20)),
        upside=float(payload.get("upside", 0.25)),
        methods_used=payload.get("methods_used", ["weighted_valuation"]),
        equity_weight=float(payload.get("equity_weight", 0.40)),
        market_weight=float(payload.get("market_weight", 0.60)),
    )
