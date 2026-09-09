from __future__ import annotations

from typing import Any


_ACTIONABLE = {"BUY", "SELL"}
_BIAS_TO_FINAL = {"BUY_BIAS": "BUY", "SELL_BIAS": "SELL"}


def _block(result: dict[str, Any], flag: str) -> dict[str, Any]:
    result["action"] = "NO_TRADE"
    result["conviction"] = 0.0
    result["final_action"] = "NO_TRADE"
    result.setdefault("risk_flags", []).append(flag)
    return result


def apply_live_market_overlay(
    decision: dict[str, Any],
    live_market_intelligence: dict[str, Any] | None,
    *,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Apply the final conservative market/session/health decision gate.

    The gate preserves the existing policy decision, but an actionable final
    decision is emitted only when the live market agrees, data is fresh, the
    market is open, the health gate is open, and the symbol belongs to the
    actionable shortlist when a shortlist is supplied.
    """
    result = dict(decision)
    if not isinstance(live_market_intelligence, dict):
        return result

    status = live_market_intelligence.get("status")
    if status in {None, "NOT_CONFIGURED"}:
        return result

    market_status = str(live_market_intelligence.get("market_status") or "OPEN").upper()
    if market_status != "OPEN":
        return _block(result, "market_session_not_open")

    if live_market_intelligence.get("health_gate") == "BLOCKED":
        return _block(result, "market_data_health_blocked")

    signals = live_market_intelligence.get("signals")
    if not isinstance(signals, list):
        return _block(result, "live_market_data_unavailable")

    candidates = [
        item for item in signals
        if isinstance(item, dict) and (symbol is None or item.get("symbol") == symbol)
    ]
    if not candidates:
        return _block(result, "live_market_symbol_unavailable") if symbol else _block(result, "live_market_signal_unavailable")

    shortlist = live_market_intelligence.get("actionable_shortlist_symbols")
    if isinstance(shortlist, list) and shortlist and symbol is not None and symbol not in shortlist:
        return _block(result, "symbol_not_in_actionable_shortlist")

    unsafe = [item for item in candidates if item.get("data_fresh") is not True]
    if unsafe:
        return _block(result, "live_market_data_stale")

    actionable = [item for item in candidates if item.get("action") in _ACTIONABLE]
    if not actionable:
        return _block(result, "live_market_signal_not_actionable")

    existing = str(result.get("action") or "NO_TRADE")
    live_sides = {str(item.get("action")) for item in actionable}
    expected = "BUY_BIAS" if "BUY" in live_sides else "SELL_BIAS"
    if existing != expected:
        return _block(result, "live_market_signal_disagrees")

    result["live_market_validated"] = True
    result["live_market_signal"] = expected.replace("_BIAS", "")
    result["final_action"] = _BIAS_TO_FINAL[expected]
    result["final_decision_policy"] = "FUNDAMENTAL_MARKET_HEALTH_SESSION_ALIGNED"
    return result
