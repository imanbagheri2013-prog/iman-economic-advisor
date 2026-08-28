from datetime import datetime, timezone

from iea.models import Observation
from iea.quality import quality
from iea.storage import Store


def test_end_to_end_observation_to_storage(tmp_path):
    now = datetime.now(timezone.utc)

    value = 4.25

    observation = Observation(
        provider="mock",
        series_id="TEST_SERIES",
        date=now,
        value=value,
        retrieved_at=now,
        quality=quality(value, now),
        status="OK",
    )

    db_path = tmp_path / "iea.sqlite3"

    store = Store(db_path)

    store.upsert(observation)

    assert store.count() == 1

    store.close()


def test_end_to_end_multiple_observations(tmp_path):
    now = datetime.now(timezone.utc)

    store = Store(tmp_path / "iea.sqlite3")

    for index in range(3):
        observation = Observation(
            provider="mock",
            series_id="TEST_SERIES",
            date=now.replace(day=index + 1),
            value=float(index + 1),
            retrieved_at=now,
            quality=quality(float(index + 1), now),
            status="OK",
        )

        store.upsert(observation)

    assert store.count() == 3

    store.close()
