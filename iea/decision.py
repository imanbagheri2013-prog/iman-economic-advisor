from __future__ import annotations

from typing import Any


_ACTIONS = ("BUY_BIAS", "HOLD", "SELL_BIAS", "NO_TRADE")


def build_decision(report: dict[str, Any]) -> dict[str, Any]:
    """Translate the aggregate eight-factor state into a conservative decision layer.

    This layer does not place orders. It exposes a directional bias only when
    coverage is sufficient and the aggregate regime is decisive enough.
    """
    score = report.get("score")
    coverage = float(report.get("coverage") or 0.0)
    regime = report.get("regime")

    if score is None or coverage < 0.625:
        return {
            "action": "NO_TRADE",
            "conviction": 0.0,
            "reason": "insufficient factor coverage for a directional decision",
        }

    score_value = float(score)
    if regime == "RISK_ON" and score_value >= 62.5:
        distance = min(1.0, (score_value - 62.5) / 37.5)
        conviction = round(0.5 + 0.5 * distance, 3)
        return {
            "action": "BUY_BIAS",
            "conviction": conviction,
            "reason": "aggregate regime is risk-on with sufficient coverage",
        }

    if regime == "RISK_OFF" and score_value <= 37.5:
        distance = min(1.0, (37.5 - score_value) / 37.5)
        conviction = round(0.5 + 0.5 * distance, 3)
        return {
            "action": "SELL_BIAS",
            "conviction": conviction,
            "reason": "aggregate regime is risk-off with sufficient coverage",
        }

    return {
        "action": "HOLD",
        "conviction": 0.5,
        "reason": "aggregate factors do not provide a decisive directional regime",
    }
