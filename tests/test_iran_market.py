from __future__ import annotations

from iea.iran_market import IranMarketAdapter, iran_factor_adapters


def test_iran_market_snapshot_and_factors(monkeypatch):
    market_rows = [
        {"insCode": "1", "lSecVal": "فلزات اساسی", "pl": 105, "py": 100, "qTotTran5J": 1000, "qTotCap": 105000, "qTitMeDem": 500, "qTitMeOf": 400},
        {"insCode": "2", "lSecVal": "بانک ها", "pl": 95, "py": 100, "qTotTran5J": 800, "qTotCap": 76000, "qTitMeDem": 300, "qTitMeOf": 500},
        {"insCode": "3", "lSecVal": "فلزات اساسی", "pl": 100, "py": 100, "qTotTran5J": 600, "qTotCap": 60000, "qTitMeDem": 250, "qTitMeOf": 250},
    ]
    client_rows = [
        {"insCode": "1", "buy_I_Value": 7000, "sell_I_Value": 4000, "buy_N_Value": 3000, "sell_N_Value": 2000},
        {"insCode": "2", "buy_I_Value": 2000, "sell_I_Value": 5000, "buy_N_Value": 1000, "sell_N_Value": 1500},
        {"insCode": "3", "buy_I_Value": 2500, "sell_I_Value": 2500, "buy_N_Value": 1000, "sell_N_Value": 1000},
    ]
    index_rows = [
        {"pClosing": 1100}, {"pClosing": 1080}, {"pClosing": 1060}, {"pClosing": 1040}, {"pClosing": 1020},
        {"pClosing": 1000}, {"pClosing": 990}, {"pClosing": 980}, {"pClosing": 970}, {"pClosing": 960},
        {"pClosing": 950}, {"pClosing": 940}, {"pClosing": 930}, {"pClosing": 920}, {"pClosing": 910},
        {"pClosing": 900}, {"pClosing": 890}, {"pClosing": 880}, {"pClosing": 870}, {"pClosing": 860},
        {"pClosing": 850},
    ]

    def fake_get(url, params=None, timeout=None, headers=None):
        class Response:
            def raise_for_status(self):
                return None

            def json(self):
                if url.endswith("/MarketData/GetMarketOverview/1"):
                    return {"marketOverview": {"indexLastValue": 1100, "indexChange": 1.85}}
                if url.endswith("/ClosingPrice/GetMarketWatch"):
                    return {"marketwatch": market_rows}
                if url.endswith("/ClientType/GetClientTypeAll"):
                    return {"clientTypeAllDto": client_rows}
                if "GetClosingPriceDailyList" in url:
                    return {"closingPriceDaily": index_rows}
                raise AssertionError(url)

        return Response()

    monkeypatch.setattr("requests.get", fake_get)
    snapshot = IranMarketAdapter().snapshot()

    assert snapshot.symbol == "IRAN_MARKET"
    assert snapshot.price == 1100
    assert snapshot.active_symbols == 3
    assert snapshot.return_1d_pct is not None
    assert snapshot.return_20d_pct is not None
    assert snapshot.bid_depth is not None
    assert snapshot.ask_depth is not None
    assert snapshot.money_flow is not None
    assert snapshot.money_flow["observed_symbols"] == 3
    assert snapshot.money_flow["market_direction"] == "INFLOW"
    assert snapshot.money_flow["top_inflow_sectors"][0]["sector"] == "فلزات اساسی"

    trend, volume, liquidity, oi, funding = iran_factor_adapters(IranMarketAdapter())
    trend_result = trend(None)
    volume_result = volume(None)
    liquidity_result = liquidity(None)
    oi_result = oi(None)
    funding_result = funding(None)

    assert trend_result.status == "OK"
    assert volume_result.status == "OK"
    assert liquidity_result.status == "OK"
    assert oi_result.status == "UNAVAILABLE"
    assert funding_result.status == "UNAVAILABLE"
