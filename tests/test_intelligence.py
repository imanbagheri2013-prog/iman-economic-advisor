from datetime import datetime, timezone

from iea.intelligence import analyze
from iea.models import Observation
from iea.storage import Store


def _obs(series_id, value, day):
    return Observation(
        provider="fred",
        series_id=series_id,
        date=datetime(2026, 8, day, tzinfo=timezone.utc),
        value=value,
        retrieved_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
        quality=100,
        status="OK",
    )


def test_intelligence_produces_regime():
    store = Store(":memory:")
    try:
        for series_id, latest, previous in [
            ("VIXCLS", 15, 20),
            ("T10Y2Y", 0.5, 0.2),
            ("DFF", 4.0, 4.5),
            ("M2SL", 22000, 21800),
            ("DCOILWTICO", 70, 80),
        ]:
            store.upsert(_obs(series_id, previous, 20))
            store.upsert(_obs(series_id, latest, 21))

        report = analyze(store)

        assert report["coverage"] == 1.0
        assert report["score"] == 75.0
        assert report["regime"] == "RISK_ON"
        assert all(item["status"] == "OK" for item in report["factors"])
    finally:
        store.close()


def test_intelligence_handles_missing_series():
    store = Store(":memory:")
    try:
        store.upsert(_obs("VIXCLS", 15, 21))
        report = analyze(store)
        assert report["regime"] == "INSUFFICIENT_DATA"
        assert report["coverage"] == 0.0
    finally:
        store.close()
