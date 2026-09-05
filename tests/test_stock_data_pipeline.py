from iea.stock_data_pipeline import build_price_batch, ingest_price_payloads
from iea.storage import Store


def payload(**overrides):
    value = {
        "insCode": "123",
        "dEven": "20260905",
        "pClosing": 100,
        "pDrCotVal": 101,
        "qTotTran5J": 1000,
        "qTotCap": 100000,
        "zTotTran": 25,
        "buyRealVolume": 600,
        "sellRealVolume": 400,
        "buyLegalVolume": 300,
        "sellLegalVolume": 500,
    }
    value.update(overrides)
    return value


def test_build_price_batch_normalizes_metrics():
    batch = build_price_batch([payload()])
    assert batch.provider == "TSETMC"
    assert batch.instruments_processed == 1
    assert batch.records_written == 9
    assert {record.series_id for record in batch.records} >= {"123.close", "123.volume", "123.buy_real_volume"}


def test_ingest_price_payloads_persists_records(tmp_path):
    store = Store(tmp_path / "market.db")
    batch = ingest_price_payloads(store, [payload(), payload(dEven="20260904", pClosing=99)])
    assert batch.records_written == 18
    assert store.count() == 18
    store.close()


def test_optional_metrics_are_skipped():
    batch = build_price_batch([payload(pDrCotVal=None, qTotCap=None, zTotTran=None)])
    assert batch.records_written == 6
    assert all(not record.series_id.endswith(".last") for record in batch.records)
