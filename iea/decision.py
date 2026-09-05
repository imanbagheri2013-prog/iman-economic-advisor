from __future__ import annotations

from typing import Any

from iea.risk import DEFAULT_RISK_POLICY, RiskPolicy


def _factor_details(report: dict[str, Any], name: str) -> dict[str, Any]:
    for factor in report.get("factors", []):
        if str(factor.get("name", "")).lower() == name.lower():
            details = factor.get("details")
            return details if isinstance(details, dict) else {}
    return {}


def _risk_assessment(report: dict[str, Any], policy: RiskPolicy = DEFAULT_RISK_POLICY) -> tuple[int, list[str]]:
    score = 0
    flags: list[str] = []

    news = _factor_details(report, "news_risk")
    if not news:
        score += policy.unavailable_news_points
        flags.append("news_risk_unavailable")
    else:
        regime = str(news.get("risk_regime", "")).upper()
        if regime == "HIGH_RISK":
            score += policy.high_news_risk_points
            flags.append("high_news_risk")
        elif regime == "ELEVATED_RISK":
            score += policy.elevated_news_risk_points
            flags.append("elevated_news_risk")

    liquidity = _factor_details(report, "liquidity")
    if not liquidity:
        score += policy.unavailable_liquidity_points
        flags.append("liquidity_unavailable")
    else:
        try:
            imbalance = abs(float(liquidity.get("depth_imbalance", 0.0)))
        except (TypeError, ValueError):
            imbalance = 0.0
        if imbalance >= policy.extreme_liquidity_imbalance:
            score += policy.extreme_liquidity_points
            flags.append("extreme_liquidity_imbalance")

    funding = _factor_details(report, "funding_rate")
    try:
        funding_pct = abs(float(funding.get("funding_rate_pct", 0.0)))
    except (TypeError, ValueError):
        funding_pct = 0.0
    if funding_pct >= policy.extreme_funding_rate_pct:
        score += policy.extreme_funding_points
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
    if (
        oi_change >= policy.oi_divergence_threshold_pct
        and trend_change >= policy.trend_divergence_threshold_pct
        and oi_sign * trend_sign < 0
    ):
        score += policy.oi_trend_divergence_points
        flags.append("oi_trend_divergence")

    return min(score, 100), flags


def _risk_tier(risk_score: int, policy: RiskPolicy = DEFAULT_RISK_POLICY) -> str:
    return policy.tier(risk_score)


def _exposure_multiplier(risk_tier: str, policy: RiskPolicy = DEFAULT_RISK_POLICY) -> float:
    """Advisory exposure budget implied by the risk tier; never executes trades."""
    return policy.exposure_multiplier(risk_tier)


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


def build_decision(report: dict[str, Any], policy: RiskPolicy = DEFAULT_RISK_POLICY) -> dict[str, Any]:
    score = report.get("score")
    coverage = float(report.get("coverage", 0.0) or 0.0)
    regime = str(report.get("regime", "")).upper()

    risk_score, risk_flags = _risk_assessment(report, policy)
    risk_tier = _risk_tier(risk_score, policy)
    risk_multiplier = round(1.0 - risk_score / 100.0, 3)
    exposure_multiplier = _exposure_multiplier(risk_tier, policy)

    base = {
        "risk_score": risk_score,
        "risk_tier": risk_tier,
        "risk_multiplier": risk_multiplier,
        "exposure_multiplier": exposure_multiplier,
        "risk_flags": risk_flags,
        "risk_rationale": _risk_rationale(risk_score, risk_tier, risk_flags),
        "exposure_rationale": _exposure_rationale(risk_tier, exposure_multiplier),
    }

    if score is None or coverage < policy.minimum_coverage:
        return {"action": "NO_TRADE", "conviction": 0.0, **base}

    if risk_tier == "CRITICAL" or "liquidity_unavailable" in risk_flags:
        return {"action": "NO_TRADE", "conviction": 0.0, **base}

    if regime == "RISK_ON" and float(score) >= policy.buy_threshold:
        conviction = min(1.0, (float(score) - policy.buy_threshold) / (100.0 - policy.buy_threshold))
        conviction = round(conviction * risk_multiplier, 3)
        return {"action": "BUY_BIAS", "conviction": conviction, **base}

    if regime == "RISK_OFF" and float(score) <= policy.sell_threshold:
        conviction = min(1.0, (policy.sell_threshold - float(score)) / policy.sell_threshold)
        conviction = round(conviction * risk_multiplier, 3)
        return {"action": "SELL_BIAS", "conviction": conviction, **base}

    conviction = round(0.5 * risk_multiplier, 3)
    return {"action": "HOLD", "conviction": conviction, **base}
