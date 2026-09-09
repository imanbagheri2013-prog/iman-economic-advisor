from __future__ import annotations

from typing import Any


_ACTIONABLE = {"BUY", "SELL"}


def build_capital_allocation(decision: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    """Apply the final capital/risk allocation gate to an advisory decision.

    Allocation is advisory-only. No order is created, submitted, or executed.
    A position can be sized only after the final investment decision is BUY/SELL
    and the existing risk engine has produced a positive position size and
    complete trade levels.
    """
    result = dict(decision)
    final_action = str(result.get("final_action") or "NO_TRADE").upper()
    capital_snapshot = result.get("portfolio")
    capital = None
    if isinstance(capital_snapshot, dict):
        capital = capital_snapshot.get("capital")
    try:
        capital_value = float(capital) if capital is not None else None
    except (TypeError, ValueError):
        capital_value = None

    if final_action not in _ACTIONABLE:
        result["exposure_budget"] = 0.0
        result["position_size"] = 0.0
        allocation = {
            "status": "BLOCKED",
            "action": "NO_TRADE",
            "capital": capital_value,
            "exposure_budget": 0.0,
            "position_size": 0.0,
            "trade_levels": None,
            "policy": "FINAL_ACTION_REQUIRED",
            "execution": "NONE",
        }
        return result, allocation

    position_size = result.get("position_size")
    trade_levels = result.get("trade_levels")
    exposure_budget = result.get("exposure_budget")
    valid_capital = capital_value is not None and capital_value > 0
    try:
        valid_position_size = position_size is not None and float(position_size) > 0
    except (TypeError, ValueError):
        valid_position_size = False
    valid_levels = isinstance(trade_levels, dict) and all(
        trade_levels.get(key) is not None for key in ("entry_price", "stop_loss", "take_profit")
    )

    if not valid_capital or not valid_position_size or not valid_levels:
        result["action"] = "NO_TRADE"
        result["final_action"] = "NO_TRADE"
        result["conviction"] = 0.0
        result["exposure_budget"] = 0.0
        result["position_size"] = 0.0
        result.setdefault("risk_flags", []).append("capital_allocation_unavailable")
        allocation = {
            "status": "BLOCKED",
            "action": "NO_TRADE",
            "capital": capital_value,
            "exposure_budget": 0.0,
            "position_size": 0.0,
            "trade_levels": None,
            "policy": "FINAL_ACTION_REQUIRED",
            "execution": "NONE",
        }
        return result, allocation

    allocation = {
        "status": "READY",
        "action": final_action,
        "capital": capital_value,
        "exposure_budget": float(exposure_budget or 0.0),
        "position_size": float(position_size),
        "trade_levels": dict(trade_levels),
        "policy": "FINAL_ACTION_RISK_CAPITAL_ALIGNED",
        "execution": "NONE",
    }
    result["capital_allocation_status"] = "READY"
    result["capital_allocation_policy"] = "FINAL_ACTION_RISK_CAPITAL_ALIGNED"
    return result, allocation
