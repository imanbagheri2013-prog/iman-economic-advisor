from __future__ import annotations

import os
from pathlib import Path

from .health import check_table_freshness
from .providers.bls import fetch_bls
from .providers.fred import fetch_fred
from .storage import DataStore

def load_config() -> dict:
return {
"fred_api_key": os.getenv("FRED_API_KEY", ""),
"bls_start_year": int(os.getenv("BLS_START_YEAR", "2021")),
"bls_end_year": int(os.getenv("BLS_END_YEAR", "2026")),
"db_path": Path(os.getenv("IEA_DB_PATH", "data/iea.sqlite3")),
}

def _bls_year_range(config: dict) -> tuple[str, str]:
start_year = str(config["bls_start_year"])
end_year = str(config["bls_end_year"])
return start_year, end_year

def pull() -> DataStore:
config = load_config()

store = DataStore(config["db_path"])

fred_data = fetch_fred(
    api_key=config["fred_api_key"],
)

bls_start_year, bls_end_year = _bls_year_range(config)

bls_data = fetch_bls(
    start_year=bls_start_year,
    end_year=bls_end_year,
)

store.save_fred(fred_data)
store.save_bls(bls_data)

return store

def pull_and_check():
store = pull()

health_results = []
health_status = "OK"

for table_name in store.table_names():
    result = check_table_freshness(
        db_path=store.path,
        table_name=table_name,
        max_age_hours=48,
    )
    health_results.append(result)

    if result.get("status") != "ok":
        health_status = "CRITICAL"

return store, health_results, health_status
