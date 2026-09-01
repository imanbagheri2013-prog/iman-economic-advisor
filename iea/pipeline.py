"""Economic data ingestion pipeline."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path

import yaml

from .health import check_all, overall_status
from .providers.bls import BLS
from .providers.fred import FRED
from .storage import Store

def load_config(path: str = "config/series.yaml") -> dict:
"""Load the configured FRED and BLS series."""
config_path = Path(path)

if not config_path.exists():
    config_path = Path(__file__).resolve().parent.parent / path

if not config_path.exists():
    raise FileNotFoundError(f"Configuration file not found: {path}")

with config_path.open(encoding="utf-8") as file:
    return yaml.safe_load(file) or {}

def _bls_year_range() -> tuple[int, int]:
"""Return the BLS year range configured for the pipeline."""
current_year = datetime.now(timezone.utc).year

start_year = int(
    os.getenv("BLS_START_YEAR", str(current_year - 5))
)

end_year = int(
    os.getenv("BLS_END_YEAR", str(current_year))
)

if start_year > end_year:
    raise ValueError(
        "BLS_START_YEAR cannot be greater than BLS_END_YEAR"
    )

return start_year, end_year

def pull(config_path: str = "config/series.yaml") -> Store:
"""Pull configured FRED and BLS observations into SQLite."""
config = load_config(config_path)

db_path = os.getenv(
    "IEA_DB_PATH",
    "data/iea.sqlite3",
)

store = Store(db_path)

fred_provider = FRED()

for series_id in config.get("fred", {}):
    observations = fred_provider.observations(
        series_id,
        limit=20,
    )

    for observation in observations:
        store.upsert(observation)

bls_start_year, bls_end_year = _bls_year_range()

bls_provider = BLS()

for series_id in config.get("bls", {}):
    observations = bls_provider.observations(
        series_id,
        bls_start_year,
        bls_end_year,
    )

    for observation in observations:
        store.upsert(observation)

return store

def pull_and_check(
config_path: str = "config/series.yaml",
) -> tuple[Store, list[dict], str]:
"""Run ingestion and evaluate the resulting data health."""
store = pull(config_path)

results = check_all(store)

status = overall_status(results)

return store, results, status
