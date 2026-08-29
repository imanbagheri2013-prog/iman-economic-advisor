from datetime import datetime, timezone

from iea.health import check_series, overall_status
from iea.models import Observation
from iea.storage import Store


def make_store(tmp_path):
    return Store(tmp_path / "health.sqlite3")


def make_observation(
    provider,
    series_id,
    value,
    observation_date,
):
    return Observation(
        provider=provider,
        series_id=series_id,
        date=observation_date,
        value=value,
        retrieved_at=datetime.now(timezone.utc),
        quality=1.0,
        status="ok",
    )


def test_check_series_healthy(tmp_path):
    store = make_store(tmp_path)

    try:
        store.upsert(
            make_observation(
                "fred",
                "CPIAUCSL",
                320.5,
                datetime(2026, 8, 1).date(),
            )
        )

        result = check_series(
            store,
            "fred",
            "CPIAUCSL",
        )

        assert result["provider"] == "fred"
        assert result["series_id"] == "CPIAUCSL"
        assert result["record_count"] == 1
        assert result["missing_count"] == 0
        assert result["status"] == "HEALTHY"

    finally:
        store.close()


def test_check_series_missing_value(tmp_path):
    store = make_store(tmp_path)

    try:
        store.upsert(
            make_observation(
                "bls",
                "CUUR0000SA0",
                None,
                datetime(2026, 8, 1).date(),
            )
        )

        result = check_series(
            store,
            "bls",
            "CUUR0000SA0",
        )

        assert result["record_count"] == 1
        assert result["missing_count"] == 1
        assert result["status"] == "WARNING"

    finally:
        store.close()


def test_check_series_not_found(tmp_path):
    store = make_store(tmp_path)

    try:
        result = check_series(
            store,
            "fred",
            "DOES_NOT_EXIST",
        )

        assert result["record_count"] == 0
        assert result["missing_count"] == 0
        assert result["status"] == "CRITICAL"

    finally:
        store.close()


def test_overall_status():
    assert overall_status(
        [
            {"status": "HEALTHY"},
            {"status": "HEALTHY"},
        ]
    ) == "HEALTHY"

    assert overall_status(
        [
            {"status": "HEALTHY"},
            {"status": "WARNING"},
        ]
    ) == "WARNING"

    assert overall_status(
        [
            {"status": "WARNING"},
            {"status": "CRITICAL"},
        ]
    ) == "CRITICAL"


def test_overall_status_empty():
    assert overall_status([]) == "CRITICAL"
