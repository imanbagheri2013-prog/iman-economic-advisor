from __future__ import annotations

import json
import os
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import requests

from .advisor import build_equity_advisor_report
from .eight_factor import analyze_eight_factor
from .equity_fundamentals import FundamentalSnapshot
from .equity_sources import fetch_live_equity_input
from .health import check_all, overall_status
from .iran_market import IranMarketAdapter
from .pipeline import pull_and_check
from .runtime import load_equity_payload

REPORT_PATH = Path("health_report.json")
MARKET_STATE_PATH = Path("iran_market_state.json")
MAX_PULL_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (2, 5)


def _save_report(payload: dict) -> None:
    REPORT_PATH.write_text(json.dumps(payload, default=str, ensure_ascii=False, indent=2), encoding="utf-8")


def _save_market_state(intelligence: dict) -> None:
    MARKET_STATE_PATH.write_text(
        json.dumps(intelligence, default=str, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def _load_market_state() -> dict | None:
    if not MARKET_STATE_PATH.exists():
        return None
    try:
        payload = json.loads(MARKET_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict):
        return None
    if payload.get("market_region") != "IRAN":
        return None
    if payload.get("data_mode") != "LIVE_MARKET":
        return None
    if payload.get("stale") is True:
        return None
    if not payload.get("generated_at") or not isinstance(payload.get("factors"), dict):
        return None
    return payload


def _market_context(now: datetime | None = None) -> tuple[str, str]:
    return IranMarketAdapter.session_state(now)


def _closed_market_intelligence(market_status: str, session_date: str) -> dict:
    previous = _load_market_state()
    if previous is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "engine": "IEA",
            "symbol": "IRAN_MARKET",
            "market_region": "IRAN",
            "market_status": market_status,
            "session_date": session_date,
            "data_mode": "NO_LIVE_MARKET_DATA",
            "stale": True,
            "score": None,
            "coverage": 0.0,
            "regime": "NEUTRAL",
            "decision": {"action": "NO_TRADE", "reason": "Iran cash market is not open and no prior live snapshot is available"},
            "factors": {},
        }

    snapshot = deepcopy(previous)
    snapshot["market_status"] = market_status
    snapshot["session_date"] = session_date
    snapshot["data_mode"] = "LAST_VALID_OPEN_SNAPSHOT"
    snapshot["stale"] = True
    snapshot["last_valid_market_snapshot_at"] = previous.get("generated_at")
    return snapshot


def _capital_from_environment() -> float | None:
    raw = os.getenv("IEA_CAPITAL")
    if raw is None or not raw.strip():
        return None
    try:
        capital = float(raw)
    except ValueError as exc:
        raise ValueError("IEA_CAPITAL must be a numeric value") from exc
    if capital < 0:
        raise ValueError("IEA_CAPITAL must be non-negative")
    return capital


def _equity_payload_path() -> Path | None:
    raw = os.getenv("IEA_EQUITY_INPUT_PATH")
    return Path(raw) if raw and raw.strip() else None


def _live_equity_symbol() -> str | None:
    raw = os.getenv("IEA_EQUITY_SYMBOL")
    return raw.strip().upper() if raw and raw.strip() else None


def _build_equity_cycle(intelligence: dict, capital: float | None) -> dict | None:
    path = _equity_payload_path()
    if path is not None and path.exists():
        payload = load_equity_payload(path)
        snapshot = FundamentalSnapshot(**payload["snapshot"])
        current_price = float(payload["current_price"])
        method_values = payload["method_values"]
        method_weights = payload["method_weights"]
        methods_used = payload.get("methods_used", ["weighted_valuation"])
        confidence = float(payload.get("confidence", 0.7))
        downside = float(payload.get("downside", 0.20))
        upside = float(payload.get("upside", 0.25))
        equity_weight = float(payload.get("equity_weight", 0.40))
        market_weight = float(payload.get("market_weight", 0.60))
    else:
        symbol = _live_equity_symbol()
        if symbol is None:
            return None
        live = fetch_live_equity_input(symbol)
        snapshot = live.snapshot
        current_price = live.current_price
        method_values = live.method_values
        method_weights = live.method_weights
        methods_used = live.methods_used
        confidence = 0.75
        downside = 0.20
        upside = 0.25
        equity_weight = 0.40
        market_weight = 0.60

    return build_equity_advisor_report(
        snapshot=snapshot,
        current_price=current_price,
        method_values=method_values,
        method_weights=method_weights,
        market_report=intelligence,
        confidence=confidence,
        downside=downside,
        upside=upside,
        methods_used=methods_used,
        equity_weight=equity_weight,
        market_weight=market_weight,
    )


def _pull_with_retry():
    last_error: requests.HTTPError | None = None
    for attempt in range(1, MAX_PULL_ATTEMPTS + 1):
        try:
            return pull_and_check()
        except requests.HTTPError as exc:
            last_error = exc
            if attempt == MAX_PULL_ATTEMPTS:
                raise
            time.sleep(RETRY_DELAYS_SECONDS[attempt - 1])
    raise last_error  # pragma: no cover


def run() -> int:
    started = datetime.now(timezone.utc).isoformat()
    store = None
    try:
        store, freshness_results, pipeline_status = _pull_with_retry()
        health_results = check_all(store)
        health_status = overall_status(health_results)
        capital = _capital_from_environment()
        market_status, session_date = _market_context()

        if market_status == "OPEN":
            intelligence = analyze_eight_factor(store, capital=capital)
            intelligence["market_status"] = market_status
            intelligence["session_date"] = session_date
            intelligence["data_mode"] = "LIVE_MARKET"
            intelligence["stale"] = False
            _save_market_state(intelligence)
        else:
            intelligence = _closed_market_intelligence(market_status, session_date)

        equity_cycle = _build_equity_cycle(intelligence, capital)

        if pipeline_status != "OK":
            status, exit_code = "error", 1
        elif health_status == "HEALTHY":
            status, exit_code = "ok", 0
        else:
            status, exit_code = "warning", 0

        payload = {
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "pipeline_status": pipeline_status,
            "health_status": health_status,
            "observations": store.count(),
            "database": str(store.path),
            "market_session": {"status": market_status, "date": session_date},
            "freshness": freshness_results,
            "health": health_results,
            "intelligence": intelligence,
        }
        if equity_cycle is not None:
            payload["advisor"] = equity_cycle
        _save_report(payload)
        print(json.dumps(payload, default=str, ensure_ascii=False, indent=2))
        return exit_code
    except Exception as exc:
        payload = {
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": "error",
            "error_type": type(exc).__name__,
            "error": str(exc),
        }
        _save_report(payload)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(run())
