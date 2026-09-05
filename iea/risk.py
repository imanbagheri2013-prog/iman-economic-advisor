from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RiskPolicy:
    """Centralized, immutable policy for advisory risk scoring and exposure."""

    high_news_risk_points: int = 60
    elevated_news_risk_points: int = 20
    unavailable_news_points: int = 25
    unavailable_liquidity_points: int = 50
    extreme_liquidity_imbalance: float = 0.35
    extreme_liquidity_points: int = 25
    extreme_funding_rate_pct: float = 0.08
    extreme_funding_points: int = 25
    oi_divergence_threshold_pct: float = 5.0
    trend_divergence_threshold_pct: float = 1.0
    oi_trend_divergence_points: int = 20
    critical_score: int = 60
    high_score: int = 40
    moderate_score: int = 20
    low_exposure: float = 1.0
    moderate_exposure: float = 0.75
    high_exposure: float = 0.5
    critical_exposure: float = 0.0

    def tier(self, risk_score: int) -> str:
        if risk_score >= self.critical_score:
            return "CRITICAL"
        if risk_score >= self.high_score:
            return "HIGH"
        if risk_score >= self.moderate_score:
            return "MODERATE"
        return "LOW"

    def exposure_multiplier(self, risk_tier: str) -> float:
        return {
            "LOW": self.low_exposure,
            "MODERATE": self.moderate_exposure,
            "HIGH": self.high_exposure,
            "CRITICAL": self.critical_exposure,
        }.get(risk_tier, 0.0)


DEFAULT_RISK_POLICY = RiskPolicy()
