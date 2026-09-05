from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FundamentalSnapshot:
    symbol: str
    revenue: float
    gross_profit: float
    operating_profit: float
    net_profit: float
    operating_cash_flow: float
    capex: float
    total_debt: float
    cash: float
    equity: float
    shares_outstanding: float
    prior_revenue: float | None = None
    prior_net_profit: float | None = None


@dataclass(frozen=True)
class FundamentalMetrics:
    gross_margin: float
    operating_margin: float
    net_margin: float
    roe: float
    debt_to_equity: float
    free_cash_flow: float
    revenue_growth: float | None
    net_profit_growth: float | None


@dataclass(frozen=True)
class FundamentalQuality:
    symbol: str
    score: float
    signal: str
    metrics: FundamentalMetrics
    reasons: tuple[str, ...]


def _positive(value: float, name: str) -> float:
    number = float(value)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def _growth(current: float, prior: float | None) -> float | None:
    if prior is None:
        return None
    prior_value = _positive(prior, "prior value")
    return float(current) / prior_value - 1.0


def calculate_fundamental_metrics(snapshot: FundamentalSnapshot) -> FundamentalMetrics:
    """Calculate normalized accounting-quality metrics from validated inputs."""
    revenue = _positive(snapshot.revenue, "revenue")
    equity = _positive(snapshot.equity, "equity")
    gross_profit = float(snapshot.gross_profit)
    operating_profit = float(snapshot.operating_profit)
    net_profit = float(snapshot.net_profit)
    debt = max(0.0, float(snapshot.total_debt))
    free_cash_flow = float(snapshot.operating_cash_flow) - max(0.0, float(snapshot.capex))
    return FundamentalMetrics(
        gross_margin=gross_profit / revenue,
        operating_margin=operating_profit / revenue,
        net_margin=net_profit / revenue,
        roe=net_profit / equity,
        debt_to_equity=debt / equity,
        free_cash_flow=free_cash_flow,
        revenue_growth=_growth(revenue, snapshot.prior_revenue),
        net_profit_growth=_growth(net_profit, snapshot.prior_net_profit) if net_profit > 0 else None,
    )


def score_fundamentals(snapshot: FundamentalSnapshot) -> FundamentalQuality:
    """Score profitability, returns, leverage, cash generation and growth.

    The result is advisory and intentionally does not imply a trade decision.
    """
    metrics = calculate_fundamental_metrics(snapshot)
    score = 50.0
    reasons: list[str] = []

    for threshold, points, label in ((0.30, 10, "strong gross margin"), (0.15, 10, "strong operating margin"), (0.10, 10, "positive net margin")):
        value = (metrics.gross_margin, metrics.operating_margin, metrics.net_margin)[(10 - points) // 0 + 0] if False else None
    if metrics.gross_margin >= 0.30:
        score += 10; reasons.append("strong gross margin")
    elif metrics.gross_margin < 0:
        score -= 10; reasons.append("negative gross margin")
    if metrics.operating_margin >= 0.15:
        score += 10; reasons.append("strong operating margin")
    elif metrics.operating_margin < 0:
        score -= 10; reasons.append("negative operating margin")
    if metrics.net_margin >= 0.10:
        score += 10; reasons.append("healthy net margin")
    elif metrics.net_margin <= 0:
        score -= 15; reasons.append("negative net profit")
    if metrics.roe >= 0.15:
        score += 10; reasons.append("strong ROE")
    elif metrics.roe < 0:
        score -= 10; reasons.append("negative ROE")
    if metrics.debt_to_equity <= 0.5:
        score += 10; reasons.append("moderate leverage")
    elif metrics.debt_to_equity > 2.0:
        score -= 15; reasons.append("high leverage")
    if metrics.free_cash_flow > 0:
        score += 10; reasons.append("positive free cash flow")
    else:
        score -= 10; reasons.append("negative free cash flow")
    if metrics.revenue_growth is not None:
        if metrics.revenue_growth >= 0.15:
            score += 5; reasons.append("strong revenue growth")
        elif metrics.revenue_growth < 0:
            score -= 5; reasons.append("declining revenue")
    if metrics.net_profit_growth is not None:
        if metrics.net_profit_growth >= 0.15:
            score += 5; reasons.append("strong profit growth")
        elif metrics.net_profit_growth < 0:
            score -= 5; reasons.append("declining profit")

    score = round(max(0.0, min(100.0, score)), 2)
    signal = "STRONG" if score >= 70 else "WEAK" if score < 40 else "NEUTRAL"
    return FundamentalQuality(str(snapshot.symbol).upper(), score, signal, metrics, tuple(reasons))


def fundamentals_summary(quality: FundamentalQuality) -> dict[str, object]:
    return {
        "symbol": quality.symbol,
        "score": quality.score,
        "signal": quality.signal,
        "metrics": quality.metrics.__dict__,
        "reasons": list(quality.reasons),
    }
