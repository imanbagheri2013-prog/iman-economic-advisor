from datetime import datetime, timezone

from iea.intelligence import analyze
from iea.models import Observation
from iea.storage import Store


def make_store(tmp_path):
    return Store(tmp_path / "intelligence.sqlite3")


def add_pair(store, series_id, latest, previous):
    now = datetime.now(timezone.utc)
    store.upsert(
        Observation(
            provider="fred",
            series_id=series_id,
            date=datetime(2026, 9, 1, tzinfo=timezone.utc),
            value=latest,
            retrieved_at=now,
            quality=100.0,
            status="OK",
        )
    )
    store.upsert(
        Observation(
            provider="fred",
            series_id=series_id,
            date=datetime(2026, 8, 31, tzinfo=timezone.utc),
            value=previous,
            retrieved_at=now,
            quality=100.0,
            status="OK",
        )
    )


def test_analyze_full_coverage(tmp_path):
    store = make_store(tmp_path)
    try:
        add_pair(store, "VIXCLS", 20.0, 21.0)
        add_pair(store, "T10Y2Y", 0.5, 0.4)
        add_pair(store, "DFF", 4.0, 4.1)
        add_pair(store, "M2SL", 22000.0, 21900.0)
        add_pair(store, "DCOILWTICO", 80.0, 78.0)

        report = analyze(store)

        assert report["engine"] == "macro_market_intelligence_v1"
        assert report["coverage"] == 1.0
        assert report["score"] is not None
        assert report["regime"] in {"RISK_ON", "NEUTRAL", "RISK_OFF"}
        assert len(report["factors"]) == 5
        assert all(item["status"] == "OK" for item in report["factors"])
    finally:
        store.close()


def test_analyze_partial_coverage(tmp_path):
    store = make_store(tmp_path)
    try:
        add_pair(store, "VIXCLS", 20.0, 21.0)

        report = analyze(store)

        assert report["coverage"] == 0.2
        assert report["score"] is not None
        assert report["regime"] in {"RISK_ON", "NEUTRAL", "RISK_OFF"}
        unavailable = [
            item for item in report["factors"] if item["status"] == "UNAVAILABLE"
        ]
        assert len(unavailable) == 4
    finally:
        store.close()


def test_analyze_no_data(tmp_path):
    store = make_store(tmp_path)
    try:
        report = analyze(store)

        assert report["score"] is None
        assert report["coverage"] == 0.0
        assert report["regime"] == "INSUFFICIENT_DATA"
        assert all(item["status"] == "UNAVAILABLE" for item in report["factors"])
    finally:
        store.close()
