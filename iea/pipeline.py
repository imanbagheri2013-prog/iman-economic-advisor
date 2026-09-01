from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from .data_freshness import check_table_freshness
from .providers.bls import BLS
from .providers.fred import FRED
from .storage import Store


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
    }


def pull(registry_path: str | Path = DEFAULT_REGISTRY) -> Store:
    config = load_config(registry_path)
    store = Store(config["db_path"])

    try:
        fred = FRED(api_key=config["fred_api_key"])
        bls = BLS(api_key=config["bls_api_key"])

        for series_id in config["fred_series"]:
            for observation in fred.observations(series_id):
                store.upsert(observation)

        for series_id in config["bls_series"]:
            observations = bls.observations(
                series_id,
                config["bls_start_year"],
                config["bls_end_year"],
            )
            for observation in observations:
                store.upsert(observation)

        return store
    except Exception:
        store.close()
        raise


def pull_and_check(registry_path: str | Path = DEFAULT_REGISTRY):
    store = pull(registry_path)
    try:
        freshness = check_table_freshness(
            db_path=store.path,
            table_name="observations",
            max_age_hours=48,
        )
        status = "OK" if freshness.get("status") == "ok" else "CRITICAL"
        return store, [freshness], status
    except Exception:
        store.close()
        raise
