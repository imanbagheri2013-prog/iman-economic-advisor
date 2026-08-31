from datetime import datetime, timedelta, timezone
from pathlib import Path
import sqlite3

from iea.data_freshness import check_table_freshness


def create_database(db_path: Path, timestamp: str):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE observations (
                id INTEGER PRIMARY KEY,
                retrieved_at TEXT
            )
            """
        )
        conn.execute(
            "INSERT INTO observations (retrieved_at) VALUES (?)",
            (timestamp,),
        )
        conn.commit()


def test_fresh_data(tmp_path: Path):
    db_path = tmp_path / "economic_data.db"

    fresh_timestamp = (
        datetime.now(timezone.utc) - timedelta(hours=1)
    ).isoformat()

    create_database(db_path, fresh_timestamp)

    result = check_table_freshness(
        db_path=db_path,
        max_age_hours=48,
    )

    assert result["status"] == "ok"
    assert result["age_hours"] <= 48


def test_stale_data(tmp_path: Path):
    db_path = tmp_path / "economic_data.db"

    stale_timestamp = (
        datetime.now(timezone.utc) - timedelta(hours=72)
    ).isoformat()

    create_database(db_path, stale_timestamp)

    result = check_table_freshness(
        db_path=db_path,
        max_age_hours=48,
    )

    assert result["status"] == "stale"


def test_missing_database(tmp_path: Path):
    db_path = tmp_path / "missing.db"

    result = check_table_freshness(
        db_path=db_path,
        max_age_hours=48,
    )

    assert result["status"] == "critical"
