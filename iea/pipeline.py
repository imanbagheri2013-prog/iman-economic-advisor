import os
from pathlib import Path

import yaml

from .providers.fred import FRED
from .providers.bls import BLS
from .storage import Store


def load_config(path="config/series.yaml"):
    """
    Load the Data Engine series configuration.

    The configuration is resolved first from the current working
    directory and then relative to the repository root.
    """
    config_path = Path(path)

    if not config_path.exists():
        config_path = Path(__file__).resolve().parent.parent / path

    if not config_path.exists():
        raise FileNotFoundError(
            f"Configuration file not found: {path}"
        )

    with config_path.open(encoding="utf-8") as file:
        return yaml.safe_load(file) or {}


def pull():
    """
    Pull configured economic observations and store them locally.
    """
    config = load_config()

    db_path = os.getenv(
        "IEA_DB_PATH",
        "data/iea.sqlite3",
    )

    store = Store(db_path)

    for series_id in config.get("fred", {}):
        provider = FRED()

        observations = provider.observations(
            series_id,
            limit=20,
        )

        for observation in observations:
            store.upsert(observation)

    for series_id in config.get("bls", {}):
        provider = BLS()

        observations = provider.observations(
            series_id,
            2020,
            2026,
        )

        for observation in observations:
            store.upsert(observation)

    return store
