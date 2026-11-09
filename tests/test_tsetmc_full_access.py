from __future__ import annotations

from iea.providers.iran_market import IranMarketProvider


def test_full_data_collects_official_tsetmc_sections(monkeypatch):
    provider = IranMarketProvider(base_url="https://example.test")
    monkeypatch.setattr(
        provider,
        "_ins_code",
        lambda symbol: ({"lVal18AFC": symbol, "insCode": "123"}, "123"),
    )

    calls = []

    def fake_get(path):
        calls.append(path)
        if path.startswith("ClosingPrice/GetClosingPriceInfo/"):
            return {"closingPriceInfo": {"pClosing": 1250}}
        if path.startswith("Instrument/GetInstrumentInfo/"):
            return {"instrumentInfo": {"eps": 100}}
        if path.startswith("Instrument/GetInstrumentIdentity/"):
            return {"instrumentIdentity": {"sector": "ساختمان"}}
        if path.startswith("ClosingPrice/GetClosingPriceDailyList/"):
            return {"closingPriceDaily": [{"dEven": 20261108, "pClosing": 1250}]}
        if path.startswith("BestLimits/"):
            return {"bestLimits": [{"number": 1}]}
        if path.startswith("Trade/GetTrade/"):
            return {"trade": [{"price": 1250}]}
        if path.startswith("Trade/GetTradeIntraDay/"):
            return {"tradeIntraDay": []}
        if path.startswith("ClientType/GetClientType/"):
            return {"clientType": [{"buy_I_Volume": 100}]}
        if path.startswith("Shareholder/GetInstrumentShareHolderLast/"):
            return {"shareHolder": []}
        if path.startswith("Instrument/GetInstrumentShareChange/"):
            return {"instrumentShareChange": []}
        if path.startswith("ClosingPrice/GetPriceAdjustList/"):
            return {"priceAdjustList": []}
        if path.startswith("Msg/GetMsgByInsCode/"):
            return {"msg": []}
        if path.startswith("MarketData/GetInstrumentStatistic/"):
            return {"instrumentStatistic": {}}
        if path.startswith("Codal/GetPreparedDataByInsCode/"):
            return {"preparedData": []}
        if path.startswith("Codal/GetStatementContentByInsCode/"):
            return {"statementContent": []}
        raise AssertionError(path)

    monkeypatch.setattr(provider, "_get", fake_get)
    result = provider.full_data("ثفارس", days=250)

    assert result["instrument"]["lVal18AFC"] == "ثفارس"
    assert result["quote"]["pClosing"] == 1250
    assert result["daily"][0]["pClosing"] == 1250
    assert result["best_limits"][0]["number"] == 1
    assert result["client_type"][0]["buy_I_Volume"] == 100
    assert result["metadata"]["provider"] == "TSETMC REST API"
    assert result["metadata"]["data_date"] == "20261108"
    assert result["metadata"]["coverage_pct"] == 100.0
    assert len(calls) == 15


def test_full_data_reports_partial_endpoint_failures(monkeypatch):
    provider = IranMarketProvider(base_url="https://example.test")
    monkeypatch.setattr(
        provider,
        "_ins_code",
        lambda symbol: ({"lVal18AFC": symbol, "insCode": "123"}, "123"),
    )

    def fake_get(path):
        if path.startswith("ClosingPrice/GetClosingPriceDailyList/"):
            return {"closingPriceDaily": [{"dEven": 20261108, "pClosing": 1250}]}
        raise RuntimeError("endpoint unavailable")

    monkeypatch.setattr(provider, "_get", fake_get)
    result = provider.full_data("ثفارس", days=30)

    assert result["daily"]
    assert result["metadata"]["coverage_pct"] < 100
    assert "quote" in result["metadata"]["failed_sections"]


def test_market_overview_collects_bourse_and_farabourse_indices(monkeypatch):
    provider = IranMarketProvider(base_url="https://example.test")

    def fake_get(path):
        if path.endswith("/1") and "GetMarketOverview" in path:
            return {"marketOverview": {"indexLastValue": 1}}
        if path.endswith("/2") and "GetMarketOverview" in path:
            return {"marketOverview": {"indexLastValue": 2}}
        if path.endswith("/All/1"):
            return {"indexB1": [{"index": "TEDPIX"}]}
        if path.endswith("/All/2"):
            return {"indexB1": [{"index": "IFX"}]}
        if path.endswith("GetSectorsSummary"):
            return {"sectorSummeries": [{"name": "ساختمان"}]}
        if path.endswith("GetInstValueAllInstAllParam"):
            return {"instValueAllInstAllParam": []}
        raise AssertionError(path)

    monkeypatch.setattr(provider, "_get", fake_get)
    result = provider.market_overview()

    assert result["bourse_overview"]["indexLastValue"] == 1
    assert result["farabourse_overview"]["indexLastValue"] == 2
    assert result["bourse_indices"][0]["index"] == "TEDPIX"
    assert result["farabourse_indices"][0]["index"] == "IFX"
    assert result["coverage_pct"] == 100.0
