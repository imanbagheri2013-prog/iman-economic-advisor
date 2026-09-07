from __future__ import annotations

from typing import Any


_ACTIONABLE = {"BUY", "SELL"}


def apply_live_market_overlay(
    decision: dict[str, Any],
    live_market_intelligence: dict[str, Any] | None,
    *,
    symbol: str | None = None,
) -> dict[str, Any]:
    """Apply a conservative live-market gate to an existing advisory decision.

    The overlay is intentionally fail-closed only when live data is explicitly
    present for the requested symbol. Unconfigured live data does not disturb
    the existing decision engine.
    """
    result = dict(decision)
    if not isinstance(live_market_intelligence, dict):
        return result

    status = live_market_intelligence.get("status")
    if status in {None, "NOT_CONFIGURED"}:
        return result

    signals = live_market_intelligence.get("signals")
    if not isinstance(signals, list):
        result["action"] = "NO_TRADE"
        result["conviction"] = 0.0
        result.setdefault("risk_flags", []).append("live_market_data_unavailable")
        return result

    candidates = [
        item for item in signals
        if isinstance(item, dict) and (symbol is None or item.get("symbol") == symbol)
    ]
    if not candidates:
        return result

    # Any explicitly stale/unsafe matching snapshot blocks action.
    unsafe = [item for item in candidates if item.get("data_fresh") is not True]
    if unsafe:
        result["action"] = "NO_TRADE"
        result["conviction"] = 0.0
        result.setdefault("risk_flags", []).append("live_market_data_stale")
        return result

    actionable = [item for item in candidates if item.get("action") in _ACTIONABLE]
    if not actionable:
        result["action"] = "NO_TRADE"
        result["conviction"] = 0.0
        result.setdefault("risk_flags", []).append("live_market_signal_not_actionable")
        return result

    # Do not allow a live signal to reverse the established policy decision.
    # It can only validate the same side; disagreement fails closed.
    existing = str(result.get("action") or "NO_TRADE")
    live_sides = {str(item.get("action")) for item in actionable}
    expected = "BUY_BIAS" if "BUY" in live_sides else "SELL_BIAS"
    if existing != expected:
        result["action"] = "NO_TRADE"
        result["conviction"] = 0.0
        result.setdefault("risk_flags", []).append("live_market_signal_disagrees")
        return result

    result["live_market_validated"] = True
    result["live_market_signal"] = expected.replace("_BIAS", "")
    return result
