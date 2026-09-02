from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any


@dataclass(frozen=True)
class Factor:
    name: str
    series_id: str
    direction: str
    weight: float


FACTORS = (
    Factor("volatility", "VIXCLS", "inverse", 1.0),
    Factor("yield_curve", "T10Y2Y", "direct", 1.0),
    Factor("policy_liquidity", "DFF", "inverse", 1.0),
    Factor("money_supply", "M2SL", "direct", 0.8),
    Factor("oil_pressure", "DCOILWTICO", "inverse", 0.7),
)


def _series_values(store: Any, series_id: str, limit: int = 2) -> list[float]:
    rows = store.con.execute(
        """
        SELECT value
        FROM observations
        WHERE provider = 'fred'
          AND series_id = ?
          AND value IS NOT NULL
        ORDER BY date DESC
        LIMIT ?
        """,
        (series_id, limit),
    ).fetchall()
    return [float(row[0]) for row in rows]


def _factor_score(values: list[float], direction: str) -> float | None:
    if len(values) < 2:
        return None
    latest, previous = values[0], values[1]
    if previous == 0:
        return None
    change_pct = (latest - previous) / abs(previous) * 100.0
    if abs(change_pct) < 0.25:
        return 50.0
    positive = change_pct > 0
    if direction == "inverse":
        positive = not positive
    return 75.0 if positive else 25.0


def analyze(store: Any) -> dict[str, Any]:
    factors: list[dict[str, Any]] = []
    weighted_total = 0.0
    weight_total = 0.0

    for factor in FACTORS:
        values = _series_values(store, factor.series_id)
        score = _factor_score(values, factor.direction)
        item = {
            "name": factor.name,
            "series_id": factor.series_id,
            "score": score,
            "weight": factor.weight,
            "observations": len(values),
            "status": "OK" if score is not None else "UNAVAILABLE",
        }
        factors.append(item)
        if score is not None:
            weighted_total += score * factor.weight
            weight_total += factor.weight

    coverage = len([item for item in factors if item["score"] is not None]) / len(factors)
    score = round(weighted_total / weight_total, 2) if weight_total else None

    if score is None:
        regime = "INSUFFICIENT_DATA"
    elif score >= 62.5:
        regime = "RISK_ON"
    elif score <= 37.5:
        regime = "RISK_OFF"
    else:
        regime = "NEUTRAL"

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": "macro_market_intelligence_v1",
        "score": score,
        "regime": regime,
        "coverage": round(coverage, 2),
        "factors": factors,
    }


def run(store: Any) -> int:
    report = analyze(store)
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0 if report["regime"] != "INSUFFICIENT_DATA" else 1


if __name__ == "__main__":
    from .config import get_settings
    from .storage import Store

    settings = get_settings()
    store = Store(settings.db_path)
    try:
        raise SystemExit(run(store))
    finally:
        store.close()
