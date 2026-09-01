from **future** import annotations

import os
from pathlib import Path
from typing import Any

from .bls import fetch_bls_data
from .fred import fetch_fred_data
from .storage import save_data

def load_config() -> dict[str, Any]:
return {
"fred_api_key": os.getenv("FRED_API_KEY"),
"bls_start_year": int(os.getenv("BLS_START_YEAR", "2021")),
"bls_end_year": int(os.getenv("BLS_END_YEAR", "2026")),
"db_path": Path(os.getenv("IEA_DB_PATH", "data/iea.sqlite3")),
}

def pull() -> dict[str, Any]:
config = load_config()

fred_data = fetch_fred_data(
    api_key=config["fred_api_key"]
)

bls_data = fetch_bls_data(
    start_year=config["bls_start_year"],
    end_year=config["bls_end_year"],
)

save_data(
    db_path=config["db_path"],
    fred_data=fred_data,
    bls_data=bls_data,
)

return {
    "fred": fred_data,
    "bls": bls_data,
    "db_path": str(config["db_path"]),
}

def pull_and_check() -> dict[str, Any]:
result = pull()

return {
    "status": "ok",
    **result,
}

if **name** == "**main**":
pull_and_check()
