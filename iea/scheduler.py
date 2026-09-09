from __future__ import annotations

import json
import logging
import os
import time
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path

import requests

from .advisor import build_equity_advisor_report
from .central_bank import build_monetary_dashboard, build_monetary_policy_index, classify_monetary_impulse, growth_rate
from .eight_factor import analyze_eight_factor
from .equity_fundamentals import FundamentalSnapshot
from .equity_sources import fetch_live_equity_input
from .health import check_all, overall_status
from .iran_market import IranMarketAdapter
from .market_intelligence import analyze_snapshots
from .pipeline import load_config, pull_and_check
from .providers.iran_market import configured_iran_symbols
from .providers.iran_market_mirror import IranMarketMirrorProvider
from .providers.market import YahooChartProvider, configured_symbols
from .runtime import load_equity_payload

LOGGER = logging.getLogger("iea.scheduler")
REPORT_PATH = Path(os.getenv("IEA_REPORT_PATH", "health_report.json"))
MARKET_STATE_PATH = Path(os.getenv("IEA_MARKET_STATE_PATH", "iran_market_state.json"))
MAX_PULL_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (2, 5)
MAX_ACTIONABLE_SIGNALS = 3


def _save_report(payload: dict) -> None:
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(json.dumps(payload, default=str, ensure_ascii=False, indent=2), encoding="utf-8")


def _publish_report(payload: dict) -> None:
    url = os.getenv("IEA_REPORT_SINK_URL")
    token = os.getenv("IEA_REPORT_SINK_TOKEN")
    if not url:
        return
    if not token:
        raise RuntimeError("IEA_REPORT_SINK_TOKEN is required when IEA_REPORT_SINK_URL is configured")
    url = url.strip()
    if not url.lower().startswith(("http://", "https://")):
        url = f"https://{url}"
    response = requests.post(url, json=payload, headers={"Authorization": f"Bearer {token}"}, timeout=20)
    response.raise_for_status()


def _save_market_state(intelligence: dict) -> None:
    MARKET_STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    MARKET_STATE_PATH.write_text(json.dumps(intelligence, default=str, ensure_ascii=False, indent=2), encoding="utf-8")


def _load_market_state() -> dict | None:
    if not MARKET_STATE_PATH.exists():
        return None
    try:
        payload = json.loads(MARKET_STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    if not isinstance(payload, dict) or payload.get("market_region") != "IRAN" or payload.get("data_mode") != "LIVE_MARKET":
        return None
    if payload.get("stale") is True:
        return None
    factors = payload.get("factors")
    if not payload.get("generated_at") or not isinstance(factors, list):
        return None
    return payload


def _market_context(now: datetime | None = None) -> tuple[str, str]:
    return IranMarketAdapter.session_state(now)


def _closed_market_intelligence(market_status: str, session_date: str) -> dict:
    previous = _load_market_state()
    if previous is None:
        return {
            "generated_at": datetime.now(timezone.utc).isoformat(), "engine": "IEA", "symbol": "IRAN_MARKET",
            "market_region": "IRAN", "market_status": market_status, "session_date": session_date,
            "data_mode": "NO_LIVE_MARKET_DATA", "stale": True, "score": None, "coverage": 0.0,
            "regime": "NEUTRAL", "decision": {"action": "NO_TRADE", "reason": "Iran cash market is not open and no prior live snapshot is available"},
            "factors": [],
        }
    snapshot = deepcopy(previous)
    previous_decision = snapshot.get("decision")
    snapshot["market_status"] = market_status
    snapshot["session_date"] = session_date
    snapshot["data_mode"] = "LAST_VALID_OPEN_SNAPSHOT"
    snapshot["stale"] = True
    snapshot["last_valid_market_snapshot_at"] = previous.get("generated_at")
    if previous_decision is not None:
        snapshot["last_valid_decision"] = previous_decision
    snapshot["decision"] = {"action": "NO_TRADE", "reason": "Iran cash market is not open; the previous live snapshot is stale and is not actionable"}
    return snapshot


def _iran_market_provider():
    """Production must use the Railway-safe GitHub mirror, never direct TSETMC."""
    mode = os.getenv("IEA_IRAN_MARKET_PROVIDER", "mirror").strip().lower()
    if mode == "direct":
        raise RuntimeError("Direct TSETMC provider is disabled in production; use IEA_IRAN_MARKET_PROVIDER=mirror")
    if mode != "mirror":
        raise RuntimeError(f"Unsupported IEA_IRAN_MARKET_PROVIDER={mode!r}; expected 'mirror'")
    return IranMarketMirrorProvider()


def _live_market_intelligence(market_status: str, mirror_health: dict | None = None) -> dict:
    """Fetch Iran symbols from the Railway-safe mirror; never analyze unhealthy mirror data."""
    iran_symbols = configured_iran_symbols()
    provider_name = "tsetmc-github-actions"
    if iran_symbols:
        symbols = iran_symbols
        provider = _iran_market_provider()
        if mirror_health and mirror_health.get("status") == "CRITICAL":
            return {
                "engine": "IEA Market Intelligence", "version": "1.1", "status": "NO_DATA",
                "market_status": market_status, "requested_symbols": symbols, "provider": provider_name,
                "actionable_count": 0, "signals": [],
                "safety": {"stale_data_action": "NO_TRADE", "closed_market_action": "NO_TRADE", "missing_required_data_action": "NO_TRADE"},
                "health_gate": "BLOCKED",
            }
    else:
        symbols = configured_symbols()
        provider = YahooChartProvider()
        provider_name = "yahoo_chart"

    if not symbols:
        return {
            "engine": "IEA Market Intelligence", "version": "1.1", "status": "NOT_CONFIGURED",
            "market_status": market_status, "actionable_count": 0, "signals": [],
            "safety": {"stale_data_action": "NO_TRADE", "closed_market_action": "NO_TRADE", "missing_required_data_action": "NO_TRADE"},
        }

    snapshots, errors = [], []
    for symbol in symbols:
        try:
            snapshots.append(provider.snapshot(symbol))
        except Exception as exc:
            errors.append({"symbol": symbol, "error_type": type(exc).__name__, "error": str(exc)})

    report = analyze_snapshots(snapshots)
    report["status"] = "OK" if snapshots else "NO_DATA"
    report["market_status"] = market_status
    report["requested_symbols"] = symbols
    report["provider"] = provider_name
    report["analysis_only_when_closed"] = True
    if mirror_health is not None:
        report["health_gate"] = "OPEN" if mirror_health.get("status") in {"HEALTHY", "WARNING"} else "BLOCKED"

    ranked = report.get("signals", [])
    actionable = [signal for signal in ranked if signal.get("action") in {"BUY", "SELL"}]
    shortlist = actionable[:MAX_ACTIONABLE_SIGNALS]
    report["actionable_shortlist"] = shortlist
    report["actionable_shortlist_symbols"] = [signal.get("symbol") for signal in shortlist]
    report["shortlist_limit"] = MAX_ACTIONABLE_SIGNALS
    report["shortlist_policy"] = "TOP_RANKED_ACTIONABLE_ADVISORY_ONLY"
    report["top_signal"] = shortlist[0] if shortlist else None

    if errors:
        report["errors"] = errors
    return report


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
        confidence, downside, upside, equity_weight, market_weight = 0.75, 0.20, 0.25, 0.40, 0.60
    return build_equity_advisor_report(snapshot=snapshot, current_price=current_price, method_values=method_values,
        method_weights=method_weights, market_report=intelligence, confidence=confidence, downside=downside,
        upside=upside, methods_used=methods_used, equity_weight=equity_weight, market_weight=market_weight)


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
    raise last_error


def _latest_pair(observations, indicator: str):
    rows = sorted((item for item in observations if item.indicator == indicator), key=lambda item: item.observed_at)
    if not rows:
        return None, None
    return rows[-1], rows[-2] if len(rows) >= 2 else None


def _growth(observations, indicator: str) -> float | None:
    latest, previous = _latest_pair(observations, indicator)
    if latest is None or previous is None:
        return None
    return growth_rate(latest.value, previous.value)


def _latest_change(observations, indicator: str) -> float | None:
    latest, previous = _latest_pair(observations, indicator)
    if latest is None or previous is None:
        return None
    return round(latest.value - previous.value, 6)


def _central_bank_report(store, config: dict) -> dict:
    observations = store.central_bank_observations()
    dashboard = build_monetary_dashboard(observations)
    base_growth, liquidity_growth, credit_growth = _growth(observations, "monetary_base"), _growth(observations, "liquidity_m2"), _growth(observations, "bank_credit")
    central_bank_credit_growth = _growth(observations, "central_bank_credit_to_banks")
    dashboard["monetary_growth"] = {"monetary_base_growth": base_growth, "liquidity_growth": liquidity_growth,
        "bank_credit_growth": credit_growth, "central_bank_credit_growth": central_bank_credit_growth}
    dashboard["monetary_impulse"] = classify_monetary_impulse(monetary_base_growth=base_growth, liquidity_growth=liquidity_growth, bank_credit_growth=credit_growth)
    dashboard["monetary_policy_index"] = build_monetary_policy_index(monetary_base_growth=base_growth, liquidity_growth=liquidity_growth,
        bank_credit_growth=credit_growth, policy_rate_change=_latest_change(observations, "policy_rate"),
        reserve_requirement_change=_latest_change(observations, "reserve_requirement"), net_open_market_operation=_latest_value(observations, "open_market_operations"),
        central_bank_credit_growth=central_bank_credit_growth)
    dashboard["policy_transmission"] = {"currency_in_circulation_growth": _growth(observations, "currency_in_circulation"),
        "bank_deposits_growth": _growth(observations, "bank_deposits"), "bank_reserves_growth": _growth(observations, "bank_reserves"),
        "government_deposits_growth": _growth(observations, "government_deposits"), "net_foreign_assets_growth": _growth(observations, "net_foreign_assets")}
    dashboard["ingestion_status"] = "CONNECTED" if config.get("cbi_data_url") and observations else ("NOT_CONFIGURED" if not config.get("cbi_data_url") else "NO_DATA")
    dashboard["stored_observation_count"] = store.count_central_bank()
    return dashboard


def _latest_value(observations, indicator: str) -> float | None:
    latest, _ = _latest_pair(observations, indicator)
    return None if latest is None else latest.value


def run() -> int:
    started = datetime.now(timezone.utc).isoformat()
    store = None
    try:
        config = load_config()
        store, pipeline_results, pipeline_status = _pull_with_retry()
        health_results = check_all(store)
        mirror_health = next(
            (item for item in pipeline_results if item.get("component") == "iran_market_mirror"),
            None,
        )
        if mirror_health is not None:
            health_results.append(mirror_health)
        health_status = overall_status(health_results)
        capital = _capital_from_environment()
        market_status, session_date = _market_context()
        if market_status == "OPEN":
            intelligence = analyze_eight_factor(store, capital=capital)
            intelligence.update({"market_status": market_status, "session_date": session_date, "data_mode": "LIVE_MARKET", "stale": False})
            _save_market_state(intelligence)
        else:
            intelligence = _closed_market_intelligence(market_status, session_date)
        live_market = _live_market_intelligence(market_status, mirror_health=mirror_health)
        equity_cycle = _build_equity_cycle(intelligence, capital)
        central_bank = _central_bank_report(store, config)
        if pipeline_status != "OK":
            status, exit_code = "error", 1
        elif health_status == "HEALTHY":
            status, exit_code = "ok", 0
        else:
            status, exit_code = "warning", 0
        freshness_results = pipeline_results
        payload = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(), "status": status,
            "pipeline_status": pipeline_status, "health_status": health_status, "observations": store.count(),
            "central_bank_observations": store.count_central_bank(), "database": str(store.path),
            "market_session": {"status": market_status, "date": session_date}, "freshness": freshness_results,
            "health": health_results, "market_data_health": mirror_health, "central_bank": central_bank, "intelligence": intelligence,
            "live_market_intelligence": live_market}
        if equity_cycle is not None:
            payload["advisor"] = equity_cycle
        _save_report(payload)
        _publish_report(payload)
        LOGGER.info(
            "IEA scheduler cycle: status=%s pipeline=%s health=%s observations=%s central_bank=%s market=%s report=%s",
            status, pipeline_status, health_status, store.count(), store.count_central_bank(), market_status, REPORT_PATH,
        )
        print(json.dumps(payload, default=str, ensure_ascii=False, indent=2))
        return exit_code
    except Exception as exc:
        payload = {"started_at": started, "finished_at": datetime.now(timezone.utc).isoformat(), "status": "error",
            "error_type": type(exc).__name__, "error": str(exc)}
        _save_report(payload)
        try:
            _publish_report(payload)
        except Exception:
            pass
        LOGGER.exception("IEA scheduler cycle failed: type=%s", type(exc).__name__)
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 1
    finally:
        if store is not None:
            store.close()


if __name__ == "__main__":
    raise SystemExit(run())
