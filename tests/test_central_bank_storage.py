from iea.central_bank import normalize_observation
from iea.storage import Store


def test_central_bank_observations_persist_and_reload(tmp_path):
    store = Store(tmp_path / "iea.sqlite3")
    try:
        observation = normalize_observation(
            "liquidity_m2",
            100.0,
            "IRR bn",
            "2026-08-31",
            frequency="monthly",
            source="CBI",
        )
        store.upsert_central_bank(observation)
        assert store.count_central_bank() == 1
        loaded = store.central_bank_observations()
        assert loaded[0].indicator == "liquidity_m2"
        assert loaded[0].value == 100.0
        assert loaded[0].frequency == "monthly"
    finally:
        store.close()


def test_central_bank_unique_key_replaces_same_source_observation(tmp_path):
    store = Store(tmp_path / "iea.sqlite3")
    try:
        first = normalize_observation("m1", 10, "IRR bn", "2026-08-31", source="CBI")
        second = normalize_observation("m1", 12, "IRR bn", "2026-08-31", source="CBI", revision=True)
        store.upsert_central_bank(first)
        store.upsert_central_bank(second)
        assert store.count_central_bank() == 1
        assert store.central_bank_observations()[0].value == 12
        assert store.central_bank_observations()[0].revision is True
    finally:
        store.close()
