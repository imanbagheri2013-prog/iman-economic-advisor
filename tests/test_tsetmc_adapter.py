import pytest

from iea.tsetmc_adapter import TsetmcClient, parse_instrument, parse_price


def test_parse_instrument_supports_tsetmc_field_names():
    item = parse_instrument({"insCode": "123", "lVal18": "TEST", "lVal30": "Test Co"})
    assert item.ins_code == "123"
    assert item.symbol == "TEST"
    assert item.name == "Test Co"


def test_parse_price_normalizes_market_fields():
    item = parse_price({
        "insCode": "123",
        "dEven": "20260905",
        "pClosing": 1250,
        "pDrCotVal": 1260,
        "qTotTran5J": 10000,
        "qTotCap": 12500000,
        "zTotTran": 350,
        "buyRealVolume": 7000,
        "sellRealVolume": 5000,
    })
    assert item.close == 1250
    assert item.last == 1260
    assert item.volume == 10000
    assert item.trade_count == 350
    assert item.buy_real_volume == 7000
    assert item.sell_real_volume == 5000


def test_parse_price_rejects_missing_close():
    with pytest.raises(ValueError):
        parse_price({"insCode": "123", "dEven": "20260905"})


def test_client_builds_tsetmc_endpoints():
    calls = []

    def transport(url):
        calls.append(url)
        return {"ok": True}

    client = TsetmcClient(transport)
    client.instrument_search("TEST")
    client.instrument_info("123")
    client.closing_prices("123", 30)
    client.client_type_history("123")
    client.shareholders("123")
    client.codal_publishers("TEST")

    assert calls[0].endswith("/Instrument/GetInstrumentSearch/TEST")
    assert calls[1].endswith("/Instrument/GetInstrumentInfo/123")
    assert calls[2].endswith("/ClosingPrice/GetClosingPriceDailyList/123/30")
    assert calls[3].endswith("/ClientType/GetClientTypeHistory/123")
    assert calls[4].endswith("/Shareholder/GetInstrumentShareHolderLast/123")
    assert calls[5].endswith("/Codal/GetCodalPublisherBySymbol/TEST")


def test_client_rejects_invalid_history_window():
    client = TsetmcClient(lambda _: None)
    with pytest.raises(ValueError):
        client.closing_prices("123", 0)
