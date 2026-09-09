from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests

OPEN_MAX_AGE_SECONDS = 30 * 60
CLOSED_MAX_AGE_SECONDS = 48 * 60 * 60


def _number(value: Any) -> float | None:
    try:
        return None if value is None else float(value)
    except (TypeError, ValueError):
        return None


def _age_seconds(value: Any) -> float | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return max(0.0, (datetime.now(timezone.utc) - parsed).total_seconds())
    except (TypeError, ValueError, OverflowError):
        return None


def check_market_mirror_health(
    url: str,
    expected_symbols: list[str] | None = None,
    timeout: float = 12.0,
) -> dict[str, Any]:
    """Validate the market-data mirror as real analysis input.

    Checks transport/JSON validity, snapshot freshness, symbol coverage,
    numeric prices, previous closes and analysis-ready active symbols.
    Suspended symbols are reported separately and are never actionable.
    """
    result: dict[str, Any] = {
        "component": "iran_market_mirror",
        "provider": "tsetmc-github-actions",
        "url": url,
        "status": "CRITICAL",
        "mirror_reachable": False,
        "generated_at": None,
        "freshness_seconds": None,
        "freshness_limit_seconds": None,
        "market_status": None,
        "expected_symbol_count": 0,
        "symbol_count": 0,
        "valid_symbol_count": 0,
        "analysis_ready_symbol_count": 0,
        "coverage": 0.0,
        "valid_symbols": [],
        "analysis_ready_symbols": [],
        "invalid_symbols": [],
        "missing_required_data": [],
        "suspended_symbols": [],
        "errors": [],
    }

    try:
        response = requests.get(url, timeout=timeout, headers={"Accept": "application/json"})
        response.raise_for_status()
        result["mirror_reachable"] = True
        payload = response.json()
        if not isinstance(payload, dict) or not isinstance(payload.get("symbols"), dict):
            raise ValueError("market mirror payload must contain a symbols object")

        symbols = payload["symbols"]
        market_status = str(payload.get("market_status") or "CLOSED").upper()
        generated_at = payload.get("generated_at")
        result["generated_at"] = generated_at
        result["market_status"] = market_status
        result["symbol_count"] = len(symbols)

        expected = [str(x).strip() for x in (expected_symbols or []) if str(x).strip()]
        target_symbols = expected or [str(x).strip() for x in symbols if str(x).strip()]
        result["expected_symbol_count"] = len(expected)
        result["coverage"] = (
            round(len(set(target_symbols).intersection(symbols)) / len(target_symbols), 4)
            if target_symbols else 0.0
        )

        age = _age_seconds(generated_at)
        limit = OPEN_MAX_AGE_SECONDS if market_status == "OPEN" else CLOSED_MAX_AGE_SECONDS
        result["freshness_seconds"] = age
        result["freshness_limit_seconds"] = limit
        if age is None:
            result["errors"].append("generated_at is missing or invalid")
        elif age > limit:
            result["errors"].append(f"mirror snapshot is stale: age_seconds={round(age, 2)}")

        for symbol in target_symbols:
            row = symbols.get(symbol)
            if not isinstance(row, dict):
                result["invalid_symbols"].append(symbol)
                result["missing_required_data"].append({"symbol": symbol, "fields": ["symbol"]})
                continue

            info = row.get("instrument_info") or {}
            instrument = row.get("instrument") or {}
            quote_status = str(info.get("quoteStatus") or "ACTIVE").upper()
            if quote_status != "ACTIVE":
                result["suspended_symbols"].append(symbol)

            missing: list[str] = []
            if not str(instrument.get("lVal18AFC") or symbol).strip():
                missing.append("symbol")
            price = _number(info.get("pClosing", info.get("pDrCotVal")))
            previous = _number(info.get("priceYesterday"))
            if price is None or price <= 0:
                missing.append("price")
            if previous is None or previous <= 0:
                missing.append("previous_close")

            if missing:
                result["invalid_symbols"].append(symbol)
                result["missing_required_data"].append({"symbol": symbol, "fields": missing})
                continue

            result["valid_symbols"].append(symbol)
            if quote_status == "ACTIVE":
                result["analysis_ready_symbols"].append(symbol)

        result["valid_symbol_count"] = len(result["valid_symbols"])
        result["analysis_ready_symbol_count"] = len(result["analysis_ready_symbols"])

        if result["errors"] or result["coverage"] < 1.0:
            result["status"] = "CRITICAL" if result["analysis_ready_symbol_count"] == 0 else "WARNING"
        elif result["analysis_ready_symbol_count"] == 0:
            result["status"] = "CRITICAL"
        elif result["suspended_symbols"]:
            result["status"] = "WARNING"
        else:
            result["status"] = "HEALTHY"
    except (requests.RequestException, ValueError, TypeError) as exc:
        result["errors"].append(f"{type(exc).__name__}: {exc}")

    return result
