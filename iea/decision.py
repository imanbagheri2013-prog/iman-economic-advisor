from __future__ import annotations

from typing import Any

from .risk import DEFAULT_RISK_POLICY, RiskPolicy
from .sizing import calculate_exposure_budget


def _risk_assessment(report: dict[str, Any], policy: RiskPolicy = DEFAULT_RISK_POLICY) -> tuple[int, list[str]]:
    score = 0
    flags: list[str] = []
    factors = report.get("factors") or []
    by_name = {factor.get("name"): factor for factor in factors if isinstance(factor, dict)}

    news = by_name.get("news_risk", {}).get("details") or {}
    news_regime = news.get("risk_regime")
    if news_regime is None:
        score += policy.unavailable_news_points
        flags.append("news_risk_unavailable")
    elif news_regime == "HIGH_RISK":
        score += policy.high_news_risk_points
        flags.append("high_news_risk")
    elif news_regime == "ELEVATED_RISK":
        score += policy.elevated_news_risk_points
        flags.append("elevated_news_risk")

    liquidity = by_name.get("liquidity", {}).get("details") or {}
    imbalance = liquidity.get("depth_imbalance")
    if imbalance is None:
        score += policy.unavailable_liquidity_points
        flags.append("liquidity_unavailable")
    elif abs(float(imbalance)) >= policy.extreme_liquidity_imbalance:
        score += policy.extreme_liquidity_points
        flags.append("extreme_liquidity_imbalance")

    funding = by_name.get("funding_rate", {}).get("details") or {}
    funding_rate = funding.get("funding_rate_pct")
    if funding_rate is not None and abs(float(funding_rate)) >= policy.extreme_funding_rate_pct:
        score += policy.extreme_funding_points
        flags.append("extreme_funding_crowding")

    oi = by_name.get("open_interest", {}).get("details") or {}
    trend = by_name.get("trend", {}).get("details") or {}
    oi_change = oi.get("oi_change_pct_1h")
    trend_return = trend.get("return_4h_pct")
    if (
        oi_change is not None
        and trend_return is not None
        and abs(float(oi_change)) >= policy.oi_divergence_threshold_pct
        and abs(float(trend_return)) >= policy.trend_divergence_threshold_pct
        and float(oi_change) * float(trend_return) < 0
    ):
        score += policy.oi_trend_divergence_points
        flags.append("oi_trend_divergence")

    return min(score, 100), flags


def _risk_tier(risk_score: int, policy: RiskPolicy = DEFAULT_RISK_POLICY) -> str:
    return policy.tier(risk_score)


def _exposure_multiplier(risk_tier: str, policy: RiskPolicy = DEFAULT_RISK_POLICY) -> float:
    return policy.exposure_multiplier(risk_tier)


def _risk_rationale(risk_score: int, risk_tier: str, flags: list[str]) -> str:
    if flags:
        return f"Risk score {risk_score}/100, tier {risk_tier}; flags: {', '.join(flags)}."
    return f"Risk score {risk_score}/100, tier {risk_tier}; no material risk flags detected."


def _exposure_rationale(exposure_multiplier: float, risk_tier: str) -> str:
    percentage = exposure_multiplier * 100
    return (
        f"Advisory exposure budget is {percentage:.0f}% at {risk_tier} risk; "
        "sizing-only guidance, never trade execution."
    )


def build_decision(report: dict[str, Any], policy: RiskPolicy = DEFAULT_RISK_POLICY) -> dict[str, Any]:
    score = report.get("score")
    coverage = float(report.get("coverage") or 0.0)
    regime = report.get("regime")

    risk_score, risk_flags = _risk_assessment(report, policy)
    risk_tier = _risk_tier(risk_score, policy)
    exposure_multiplier = _exposure_multiplier(risk_tier, policy)

    if score is None or coverage < policy.minimum_coverage:
        action = "NO_TRADE"
    elif "high_news_risk" in risk_flags or "liquidity_unavailable" in risk_flags or risk_score >= policy.critical_score:
        action = "NO_TRADE"
    elif regime == "RISK_ON" and float(score) >= policy.buy_threshold:
        action = "BUY_BIAS"
    elif regime == "RISK_OFF" and float(score) <= policy.sell_threshold:
        action = "SELL_BIAS"
    else:
        action = "HOLD"

    conviction = 0.0 if score is None else min(1.0, abs(float(score) - 50.0) / 50.0)
    risk_multiplier = max(0.0, 1.0 - risk_score / 100.0)
    conviction *= risk_multiplier

    capital = report.get("capital")
    exposure_budget = None
    if capital is not None:
        exposure_budget = calculate_exposure_budget(capital, exposure_multiplier)

    result = {
        "action": action,
        "conviction": conviction,
        "risk_score": risk_score,
        "risk_flags": risk_flags,
        "risk_tier": risk_tier,
        "risk_multiplier": risk_multiplier,
        "exposure_multiplier": exposure_multiplier,
        "risk_rationale": _risk_rationale(risk_score, risk_tier, risk_flags),
        "exposure_rationale": _exposure_rationale(exposure_multiplier, risk_tier),
    }
    if exposure_budget is not None:
        result["exposure_budget"] = exposure_budget
        result["sizing_rationale"] = (
            f"Capital-based advisory budget: {exposure_budget:.2f} from capital {float(capital):.2f} "
            f"at {exposure_multiplier:.0%} exposure; no trade is executed."
        )
    return result
