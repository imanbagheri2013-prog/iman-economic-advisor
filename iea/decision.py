from __future__ import annotations

from typing import Any


BUY_THRESHOLD = 62.5
SELL_THRESHOLD = 37.5
MIN_COVERAGE = 0.625


def _factor_details(report: dict[str, Any], name: str) -> dict[str, Any]:
    for factor in report.get("factors", []):
        if str(factor.get("name", "")).lower() == name.lower():
            details = factor.get("details")
            return details if isinstance(details, dict) else {}
    return {}


def _risk_assessment(report: dict[str, Any]) -> tuple[int, list[str]]:
    score = 0
    flags: list[str] = []

    news = _factor_details(report, "news_risk")
    if not news:
        score += 25
        flags.append("news_risk_unavailable")
    else:
        regime = str(news.get("risk_regime", "")).upper()
        if regime == "HIGH_RISK":
            score += 60
            flags.append("high_news_risk")
        elif regime == "ELEVATED_RISK":
            score += 20
            flags.append("elevated_news_risk")

    liquidity = _factor_details(report, "liquidity")
    if not liquidity:
        score += 50
        flags.append("liquidity_unavailable")
    else:
        try:
            imbalance = abs(float(liquidity.get("depth_imbalance", 0.0)))
        except (TypeError, ValueError):
            imbalance = 0.0
        if imbalance >= 0.35:
            score += 25
            flags.append("extreme_liquidity_imbalance")

    funding = _factor_details(report, "funding_rate")
    try:
        funding_pct = abs(float(funding.get("funding_rate_pct", 0.0)))
    except (TypeError, ValueError):
        funding_pct = 0.0
    if funding_pct >= 0.08:
        score += 25
        flags.append("extreme_funding_crowding")

    oi = _factor_details(report, "open_interest")
    trend = _factor_details(report, "trend")
    try:
        oi_change = abs(float(oi.get("oi_change_pct_1h", 0.0)))
        trend_change = abs(float(trend.get("return_4h_pct", 0.0)))
        oi_sign = float(oi.get("oi_change_pct_1h", 0.0))
        trend_sign = float(trend.get("return_4h_pct", 0.0))
    except (TypeError, ValueError):
        oi_change = trend_change = oi_sign = trend_sign = 0.0
    if oi_change >= 5.0 and trend_change >= 1.0 and oi_sign * trend_sign < 0:
        score += 20
        flags.append("oi_trend_divergence")

    return min(score, 100), flags


def _risk_tier(risk_score: int) -> str:
    if risk_score >= 60:
        return "CRITICAL"
    if risk_score >= 40:
        return "HIGH"
    if risk_score >= 20:
        return "MODERATE"
    return "LOW"


def _exposure_multiplier(risk_tier: str) -> float:
    """Advisory exposure budget implied by the risk tier; never executes trades."""
    return {
        "LOW": 1.0,
        "MODERATE": 0.75,
        "HIGH": 0.5,
        "CRITICAL": 0.0,
    }.get(risk_tier, 0.0)


def _risk_rationale(risk_score: int, risk_tier: str, risk_flags: list[str]) -> str:
    if not risk_flags:
        return f"Risk score {risk_score}/100: no material risk flags; {risk_tier} risk budget applies."
    labels = ", ".join(risk_flags)
    return f"Risk score {risk_score}/100: {labels}; {risk_tier} risk budget applies."


def _exposure_rationale(risk_tier: str, exposure_multiplier: float) -> str:
    if exposure_multiplier <= 0.0:
        return "Advisory exposure budget is 0% because the risk tier is CRITICAL."
    return (
        f"Advisory exposure budget is {exposure_multiplier:.0%} for {risk_tier} risk; "
        "this is a sizing constraint only and never executes a trade."
    )


def build_decision(report: dict[str, Any]) -> dict[str, Any]:
    score = report.get("score")
    coverage = float(report.get("coverage", 0.0) or 0.0)
    regime = str(report.get("regime", "")).upper()

    risk_score, risk_flags = _risk_assessment(report)
    risk_tier = _risk_tier(risk_score)
    risk_multiplier = round(1.0 - risk_score / 100.0, 3)
    exposure_multiplier = _exposure_multiplier(risk_tier)

    base = {
        "risk_score": risk_score,
        "risk_tier": risk_tier,
        "risk_multiplier": risk_multiplier,
        "exposure_multiplier": exposure_multiplier,
        "risk_flags": risk_flags,
        "risk_rationale": _risk_rationale(risk_score, risk_tier, risk_flags),
        "exposure_rationale": _exposure_rationale(risk_tier, exposure_multiplier),
    }

    if score is None or coverage < MIN_COVERAGE:
        return {"action": "NO_TRADE", "conviction": 0.0, **base}

    if risk_tier == "CRITICAL" or "liquidity_unavailable" in risk_flags:
        return {"action": "NO_TRADE", "conviction": 0.0, **base}

    if regime == "RISK_ON" and float(score) >= BUY_THRESHOLD:
        conviction = min(1.0, (float(score) - BUY_THRESHOLD) / (100.0 - BUY_THRESHOLD))
        conviction = round(conviction * risk_multiplier, 3)
        return {"action": "BUY_BIAS", "conviction": conviction, **base}

    if regime == "RISK_OFF" and float(score) <= SELL_THRESHOLD:
        conviction = min(1.0, (SELL_THRESHOLD - float(score)) / SELL_THRESHOLD)
        conviction = round(conviction * risk_multiplier, 3)
        return {"action": "SELL_BIAS", "conviction": conviction, **base}

    conviction = round(0.5 * risk_multiplier, 3)
    return {"action": "HOLD", "conviction": conviction, **base}
