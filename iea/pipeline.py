from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Any

import yaml

from .central_bank_provider import fetch_observations
from .data_freshness import check_table_freshness
from .health import check_market_mirror_health
from .providers.bls import BLS
from .providers.fred import FRED
from .providers.iran_market import configured_iran_symbols
from .providers.iran_market_mirror import DEFAULT_MIRROR_URL
from .storage import Store

LOGGER = logging.getLogger("iea.pipeline")
DEFAULT_REGISTRY = Path("config/series.yaml")
DEFAULT_DB = Path("data/iea.sqlite3")


def load_config(registry_path: str | Path = DEFAULT_REGISTRY) -> dict[str, Any]:
    path = Path(registry_path)
    if not path.exists():
        raise FileNotFoundError(f"Series registry not found: {path}")
    with path.open("r", encoding="utf-8") as fh:
        registry = yaml.safe_load(fh) or {}
    return {
        "fred_api_key": os.getenv("FRED_API_KEY"),
        "bls_api_key": os.getenv("BLS_API_KEY"),
        "bls_start_year": int(os.getenv("BLS_START_YEAR", "2021")),
        "bls_end_year": int(os.getenv("BLS_END_YEAR", "2026")),
        "db_path": Path(os.getenv("IEA_DB_PATH", str(DEFAULT_DB))),
        "registry_path": path,
        "fred_series": list((registry.get("fred") or {}).keys()),
        "bls_series": list((registry.get("bls") or {}).keys()),
        "cbi_data_url": os.getenv("IEA_CBI_DATA_URL", "").strip() or None,
        "closed_dates": [value.strip() for value in os.getenv("IEA_CLOSED_DATES", "").split(",") if value.strip()],
        "iran_market_mirror_url": os.getenv("IEA_IRAN_MARKET_MIRROR_URL", DEFAULT_MIRROR_URL).strip(),
        "iran_symbols": configured_iran_symbols(),
    }


def pull(registry_path: str | Path = DEFAULT_REGISTRY) -> Store:
    config = load_config(registry_path)
    store = Store(config["db_path"])
    try:
        fred = FRED(api_key=config["fred_api_key"])
        bls = BLS(api_key=config["bls_api_key"])
        for series_id in config["fred_series"]:
            try:
                for observation in fred.observations(series_id):
                    store.upsert(observation)
            except Exception as exc:
                LOGGER.warning("FRED series failed: series=%s type=%s error=%s", series_id, type(exc).__name__, exc)
        for series_id in config["bls_series"]:
            try:
                observations = bls.observations(series_id, config["bls_start_year"], config["bls_end_year"])
                for observation in observations:
                    store.upsert(observation)
            except Exception as exc:
                LOGGER.warning("BLS series failed: series=%s type=%s error=%s", series_id, type(exc).__name__, exc)
        if config["cbi_data_url"]:
            try:
                for observation in fetch_observations(config["cbi_data_url"], timeout=12):
                    store.upsert_central_bank(observation)
            except Exception as exc:
                LOGGER.warning("CBI source failed: type=%s error=%s", type(exc).__name__, exc)
        return store
    except Exception:
        store.close()
        raise


def pull_and_check(registry_path: str | Path = DEFAULT_REGISTRY):
    """Run macro ingestion and validate the Iran market-data mirror."""
    config = load_config(registry_path)
    store = pull(registry_path)
    try:
        freshness = check_table_freshness(
            db_path=store.path,
            table_name="observations",
            max_age_hours=48,
            closed_weekdays={5, 6},
            closed_dates=config["closed_dates"],
        )
        results = [freshness]
        if config["iran_symbols"]:
            results.append(check_market_mirror_health(
                config["iran_market_mirror_url"],
                expected_symbols=config["iran_symbols"],
            ))
        status = "OK" if all(item.get("status") != "CRITICAL" for item in results) else "CRITICAL"
        return store, results, status
    except Exception:
        store.close()
        raise
