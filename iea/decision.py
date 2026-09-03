from __future__ import annotations

from typing import Any


_ACTIONS = ("BUY_BIAS", "HOLD", "SELL_BIAS", "NO_TRADE")


def _risk_assessment(report: dict[str, Any]) -> tuple[int, list[str]]:
    """Score execution risk from factor availability and adverse market conditions."""
    risk_score = 0
    flags: list[str] = []
    factors = report.get("factors") or []
    by_name = {factor.get("name"): factor for factor in factors if isinstance(factor, dict)}

    news = by_name.get("news_risk")
    news_details = (news or {}).get("details") or {}
    if (news or {}).get("status") == "UNAVAILABLE":
        risk_score += 25
        flags.append("news_risk_unavailable")
    elif news_details.get("risk_regime") == "HIGH_RISK":
        risk_score += 60
        flags.append("high_news_risk")
    elif news_details.get("risk_regime") == "ELEVATED_RISK":
        risk_score += 20
        flags.append("elevated_news_risk")

    liquidity = by_name.get("liquidity")
    liquidity_details = (liquidity or {}).get("details") or {}
    if (liquidity or {}).get("status") == "UNAVAILABLE":
        risk_score += 50
        flags.append("liquidity_unavailable")
    else:
        try:
            imbalance = abs(float(liquidity_details.get("depth_imbalance")))
        except (TypeError, ValueError):
            imbalance = 0.0
        if imbalance >= 0.35:
            risk_score += 25
            flags.append("extreme_liquidity_imbalance")

    funding = by_name.get("funding_rate")
    funding_details = (funding or {}).get("details") or {}
    try:
        funding_pct = abs(float(funding_details.get("funding_rate_pct")))
    except (TypeError, ValueError):
        funding_pct = 0.0
    if funding_pct >= 0.08:
        risk_score += 25
        flags.append("extreme_funding_crowding")

    oi = by_name.get("open_interest")
    trend = by_name.get("trend")
    oi_details = (oi or {}).get("details") or {}
    trend_details = (trend or {}).get("details") or {}
    try:
        oi_change = float(oi_details.get("oi_change_pct_1h"))
        trend_change = float(trend_details.get("return_4h_pct"))
    except (TypeError, ValueError):
        oi_change = 0.0
        trend_change = 0.0
    if abs(oi_change) >= 5.0 and abs(trend_change) >= 1.0 and oi_change * trend_change < 0:
        risk_score += 20
        flags.append("oi_trend_divergence")

    return min(100, risk_score), flags


def build_decision(report: dict[str, Any]) -> dict[str, Any]:
    """Translate aggregate factors into a conservative directional decision."""
    score = report.get("score")
    coverage = float(report.get("coverage") or 0.0)
    regime = report.get("regime")
    risk_score, risk_flags = _risk_assessment(report)

    base = {
        "risk_score": risk_score,
        "risk_flags": risk_flags,
    }

    if score is None or coverage < 0.625:
        return {
            **base,
            "action": "NO_TRADE",
            "conviction": 0.0,
            "reason": "insufficient factor coverage for a directional decision",
        }

    if "high_news_risk" in risk_flags or "liquidity_unavailable" in risk_flags or risk_score >= 60:
        return {
            **base,
            "action": "NO_TRADE",
            "conviction": 0.0,
            "reason": "risk gate blocked the directional decision",
        }

    score_value = float(score)
    if regime == "RISK_ON" and score_value >= 62.5:
        distance = min(1.0, (score_value - 62.5) / 37.5)
        conviction = round(0.5 + 0.5 * distance, 3)
        conviction = round(conviction * (1.0 - risk_score / 100.0), 3)
        return {
            **base,
            "action": "BUY_BIAS",
            "conviction": conviction,
            "reason": "aggregate regime is risk-on with sufficient coverage and passed the risk gate",
        }

    if regime == "RISK_OFF" and score_value <= 37.5:
        distance = min(1.0, (37.5 - score_value) / 37.5)
        conviction = round(0.5 + 0.5 * distance, 3)
        conviction = round(conviction * (1.0 - risk_score / 100.0), 3)
        return {
            **base,
            "action": "SELL_BIAS",
            "conviction": conviction,
            "reason": "aggregate regime is risk-off with sufficient coverage and passed the risk gate",
        }

    return {
        **base,
        "action": "HOLD",
        "conviction": round(0.5 * (1.0 - risk_score / 100.0), 3),
        "reason": "aggregate factors do not provide a decisive directional regime",
    }
