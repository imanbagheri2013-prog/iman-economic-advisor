from __future__ import annotations

from dataclasses import dataclass
from statistics import mean, median
from typing import Iterable


@dataclass(frozen=True)
class ValuationScenario:
    name: str
    fair_value: float
    upside_pct: float
    method: str
    confidence: float


@dataclass(frozen=True)
class EquityValuation:
    symbol: str
    current_price: float
    intrinsic_value: float
    bear_value: float
    base_value: float
    bull_value: float
    scenarios: tuple[ValuationScenario, ...]
    methods_used: tuple[str, ...]


def _positive(value: float, name: str) -> float:
    number = float(value)
    if number <= 0:
        raise ValueError(f"{name} must be positive")
    return number


def dcf_equity_value(
    fcff: Iterable[float],
    discount_rate: float,
    terminal_growth: float,
    net_debt: float = 0.0,
    shares_outstanding: float = 1.0,
) -> float:
    """Estimate equity value per share from a FCFF DCF model."""
    cash_flows = [float(value) for value in fcff]
    if not cash_flows or any(value < 0 for value in cash_flows):
        raise ValueError("fcff must contain non-negative forecast cash flows")
    rate = float(discount_rate)
    growth = float(terminal_growth)
    if rate <= growth or rate <= 0:
        raise ValueError("discount_rate must be positive and greater than terminal_growth")
    shares = _positive(shares_outstanding, "shares_outstanding")

    enterprise_value = sum(value / (1.0 + rate) ** period for period, value in enumerate(cash_flows, 1))
    terminal_value = cash_flows[-1] * (1.0 + growth) / (rate - growth)
    enterprise_value += terminal_value / (1.0 + rate) ** len(cash_flows)
    equity_value = enterprise_value - float(net_debt)
    return equity_value / shares


def pe_value(eps: float, peer_pe: float) -> float:
    """Value a share using EPS and a reference P/E multiple."""
    return _positive(eps, "eps") * _positive(peer_pe, "peer_pe")


def ev_ebitda_equity_value(
    ebitda: float,
    peer_ev_ebitda: float,
    net_debt: float,
    shares_outstanding: float,
) -> float:
    """Convert EV/EBITDA valuation into equity value per share."""
    enterprise_value = _positive(ebitda, "ebitda") * _positive(peer_ev_ebitda, "peer_ev_ebitda")
    shares = _positive(shares_outstanding, "shares_outstanding")
    return (enterprise_value - float(net_debt)) / shares


def weighted_fair_value(values: Iterable[float], weights: Iterable[float]) -> float:
    """Combine independent valuation methods with normalized weights."""
    observations = [float(value) for value in values]
    weight_values = [float(weight) for weight in weights]
    if not observations or len(observations) != len(weight_values):
        raise ValueError("values and weights must be non-empty and have equal length")
    if any(value <= 0 for value in observations):
        raise ValueError("valuation values must be positive")
    if any(weight < 0 for weight in weight_values) or sum(weight_values) <= 0:
        raise ValueError("weights must be non-negative and have a positive sum")
    total = sum(weight_values)
    return sum(value * weight for value, weight in zip(observations, weight_values)) / total


def scenario_values(base_value: float, downside: float = 0.20, upside: float = 0.25) -> tuple[float, float, float]:
    """Create bear/base/bull valuation bands around a base estimate."""
    base = _positive(base_value, "base_value")
    down = float(downside)
    up = float(upside)
    if not 0 <= down < 1 or up < 0:
        raise ValueError("downside must be in [0,1) and upside must be non-negative")
    return base * (1.0 - down), base, base * (1.0 + up)


def build_equity_valuation(
    symbol: str,
    current_price: float,
    method_values: Iterable[float],
    method_weights: Iterable[float],
    confidence: float = 0.7,
    downside: float = 0.20,
    upside: float = 0.25,
    methods_used: Iterable[str] = ("weighted_valuation",),
) -> EquityValuation:
    """Build a scenario-based advisory equity valuation.

    This layer is deliberately independent from source acquisition. Financial
    statements, market prices, macro forecasts and peer multiples are supplied
    by the data layer and must be validated before use.
    """
    price = _positive(current_price, "current_price")
    base = weighted_fair_value(method_values, method_weights)
    bear, base, bull = scenario_values(base, downside, upside)
    confidence_value = float(confidence)
    if not 0 <= confidence_value <= 1:
        raise ValueError("confidence must be between 0 and 1")

    method_names = tuple(str(method) for method in methods_used)
    scenarios = tuple(
        ValuationScenario(name, value, (value / price - 1.0) * 100.0, 
                          "scenario", confidence_value if name == "BASE" else confidence_value * 0.8)
        for name, value in (("BEAR", bear), ("BASE", base), ("BULL", bull))
    )
    return EquityValuation(
        symbol=str(symbol).upper(),
        current_price=price,
        intrinsic_value=base,
        bear_value=bear,
        base_value=base,
        bull_value=bull,
        scenarios=scenarios,
        methods_used=method_names,
    )


def valuation_summary(valuation: EquityValuation) -> dict[str, object]:
    """Serialize an equity valuation into a stable report structure."""
    return {
        "symbol": valuation.symbol,
        "current_price": valuation.current_price,
        "intrinsic_value": valuation.intrinsic_value,
        "bear_value": valuation.bear_value,
        "base_value": valuation.base_value,
        "bull_value": valuation.bull_value,
        "upside_to_intrinsic_pct": (valuation.intrinsic_value / valuation.current_price - 1.0) * 100.0,
        "methods_used": list(valuation.methods_used),
        "scenarios": [
            {
                "name": scenario.name,
                "fair_value": scenario.fair_value,
                "upside_pct": scenario.upside_pct,
                "method": scenario.method,
                "confidence": scenario.confidence,
            }
            for scenario in valuation.scenarios
        ],
    }
