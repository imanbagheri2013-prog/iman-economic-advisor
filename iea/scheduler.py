from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

from .advisor import build_equity_advisor_report
from .eight_factor import analyze_eight_factor
from .equity_fundamentals import FundamentalSnapshot
from .health import check_all, overall_status
from .pipeline import pull_and_check
from .runtime import load_equity_payload


REPORT_PATH = Path("health_report.json")
MAX_PULL_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (2, 5)


def _save_report(payload: dict) -> None:
    REPORT_PATH.write_text(
        json.dumps(payload, default=str, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


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
    if raw is None or not raw.strip():
        return None
    return Path(raw)


def _build_equity_cycle(intelligence: dict, capital: float | None) -> dict | None:
    path = _equity_payload_path()
    if path is None or not path.exists():
        return None

    payload = load_equity_payload(path)
    snapshot = FundamentalSnapshot(**payload["snapshot"])
    return build_equity_advisor_report(
        snapshot=snapshot,
        current_price=float(payload["current_price"]),
        method_values=payload["method_values"],
        method_weights=payload["method_weights"],
        market_report=intelligence["summary"],
        confidence=float(payload.get("confidence", 0.7)),
        downside=float(payload.get("downside", 0.20)),
        upside=float(payload.get("upside", 0.25)),
        methods_used=payload.get("methods_used", ["weighted_valuation"]),
        equity_weight=float(payload.get("equity_weight", 0.40)),
        market_weight=float(payload.get("market_weight", 0.60)),
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
        intelligence = analyze_eight_factor(store, capital=capital)
        equity_cycle = _build_equity_cycle(intelligence, capital)

        if pipeline_status != "OK":
            status = "error"
            exit_code = 1
        elif health_status == "HEALTHY":
            status = "ok"
            exit_code = 0
        else:
            status = "warning"
            exit_code = 0

        payload = {
            "started_at": started,
            "finished_at": datetime.now(timezone.utc).isoformat(),
            "status": status,
            "pipeline_status": pipeline_status,
            "health_status": health_status,
            "observations": store.count(),
            "database": str(store.path),
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
