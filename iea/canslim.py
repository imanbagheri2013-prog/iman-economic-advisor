from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CanSlimInput:
    """Data required for a CAN SLIM-style stock review.

    None means the criterion was not supplied; the engine never invents a
    fundamental value. This is especially important for Iran-market symbols,
    where some fundamentals must come from Codal/company reports.
    """

    current_eps_growth_pct: float | None = None
    annual_eps_growth_pct: float | None = None
    new_catalyst: bool | None = None
    price_near_high: bool | None = None
    demand_score: float | None = None
    leader_score: float | None = None
    institutional_sponsorship_score: float | None = None
    market_trend_score: float | None = None


def analyze_canslim(symbol: str, data: CanSlimInput) -> dict[str, Any]:
    """Return a transparent CAN SLIM-style score without fabricating missing data.

    Thresholds are conservative heuristics inspired by the CAN SLIM framework;
    the result is an analytical score, not an IBD rating or proprietary score.
    """
    criteria: dict[str, dict[str, Any]] = {}

    def criterion(name: str, value: bool | None, reason: str) -> None:
        criteria[name] = {"pass": value, "reason": reason}

    c_pass = data.current_eps_growth_pct is not None and data.current_eps_growth_pct >= 20
    criterion("C", c_pass if data.current_eps_growth_pct is not None else None,
              "current EPS growth >= 20%" if data.current_eps_growth_pct is not None else "current EPS growth unavailable")

    a_pass = data.annual_eps_growth_pct is not None and data.annual_eps_growth_pct >= 20
    criterion("A", a_pass if data.annual_eps_growth_pct is not None else None,
              "annual EPS growth >= 20%" if data.annual_eps_growth_pct is not None else "annual EPS growth unavailable")

    criterion("N", data.new_catalyst, "new catalyst confirmed" if data.new_catalyst else ("no new catalyst confirmed" if data.new_catalyst is False else "new catalyst unavailable"))

    criterion("S", None if data.demand_score is None else data.demand_score >= 60,
              "demand score >= 60" if data.demand_score is not None else "supply/demand data unavailable")
    criterion("L", None if data.leader_score is None else data.leader_score >= 60,
              "leader score >= 60" if data.leader_score is not None else "relative-strength/leadership data unavailable")
    criterion("I", None if data.institutional_sponsorship_score is None else data.institutional_sponsorship_score >= 60,
              "institutional sponsorship score >= 60" if data.institutional_sponsorship_score is not None else "institutional sponsorship data unavailable")
    criterion("M", None if data.market_trend_score is None else data.market_trend_score >= 60,
              "market trend score >= 60" if data.market_trend_score is not None else "market trend data unavailable")

    n = 0
    p = 0
    for item in criteria.values():
        if item["pass"] is not None:
            n += 1
            p += int(item["pass"])

    if data.price_near_high is not None:
        n += 1
        p += int(data.price_near_high)
        criteria["price_position"] = {
            "pass": data.price_near_high,
            "reason": "price is near its recent high" if data.price_near_high else "price is not near its recent high",
        }

    score = round((p / n) * 100.0, 2) if n else 0.0
    missing = [key for key, value in criteria.items() if value["pass"] is None]
    action = "WATCH" if score >= 70 and not missing else "WAIT"
    if score >= 85 and not missing:
        action = "CANSLIM_CANDIDATE"

    return {
        "symbol": symbol,
        "method": "CAN SLIM-style",
        "score": score,
        "action": action,
        "criteria": criteria,
        "evaluated_criteria": n,
        "missing_criteria": missing,
        "disclaimer": "Heuristic CAN SLIM-style analysis; not an official IBD/O'Neil rating.",
    }
