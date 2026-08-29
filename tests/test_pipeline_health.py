from datetime import date, datetime, timezone

from iea.pipeline import pull_and_check
from iea.storage import Store

def test_pull_and_check(tmp_path, monkeypatch):
db_path = tmp_path / "pipeline-health.sqlite3"

```
monkeypatch.setenv(
    "IEA_DB_PATH",
    str(db_path),
)

monkeypatch.setenv(
    "BLS_START_YEAR",
    "2025",
)

monkeypatch.setenv(
    "BLS_END_YEAR",
    "2026",
)

store = Store(db_path)

try:
    from iea.models import Observation

    store.upsert(
        Observation(
            provider="fred",
            series_id="TEST_FRED",
            date=date(2026, 8, 1),
            value=100.0,
            retrieved_at=datetime.now(timezone.utc),
            quality=1.0,
            status="ok",
        )
    )

finally:
    store.close()

class FakeProvider:
    def observations(self, series_id, *args, **kwargs):
        return [
            Observation(
                provider="fred",
                series_id=series_id,
                date=date(2026, 8, 1),
                value=100.0,
                retrieved_at=datetime.now(timezone.utc),
                quality=1.0,
                status="ok",
            )
        ]

monkeypatch.setattr(
    "iea.pipeline.FRED",
    FakeProvider,
)

class FakeBLSProvider:
    def observations(self, series_id, *args, **kwargs):
        return [
            Observation(
                provider="bls",
                series_id=series_id,
                date=date(2026, 8, 1),
                value=200.0,
                retrieved_at=datetime.now(timezone.utc),
                quality=1.0,
                status="ok",
            )
        ]

monkeypatch.setattr(
    "iea.pipeline.BLS",
    FakeBLSProvider,
)

config_path = tmp_path / "series.yaml"

config_path.write_text(
    """
```

fred:
TEST_FRED: "Test FRED"

bls:
TEST_BLS: "Test BLS"
""",
encoding="utf-8",
)

```
store, results, status = pull_and_check(
    str(config_path)
)

try:
    assert db_path.exists()

    assert len(results) == 2

    providers = {
        result["provider"]
        for result in results
    }

    assert providers == {
        "fred",
        "bls",
    }

    assert status == "HEALTHY"

    for result in results:
        assert result["record_count"] > 0
        assert result["missing_count"] == 0
        assert result["status"] == "HEALTHY"

finally:
    store.close()
```
