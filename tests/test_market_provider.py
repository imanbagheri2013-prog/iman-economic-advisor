from datetime import datetime, timezone

import pytest

from iea.providers.market import YahooChartProvider, configured_symbols


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code
        self.headers = {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


def test_yahoo_provider_normalizes_chart_payload(monkeypatch):
    payload = {
        "chart": {
            "result": [{
                "meta": {
                    "regularMarketPrice": 105.0,
                    "regularMarketTime": 1_700_000_000,
                    "previousClose": 100.0,
                    "averageDailyVolume3Month": 1000,
                },
                "indicators": {
                    "quote": [{
                        "volume": [800, 1600],
                        "high": [106],
                        "low": [99],
                    }]
                },
            }]
        }
    }

    monkeypatch.setattr("iea.providers.market.requests.get", lambda *args, **kwargs: FakeResponse(payload))
    snapshot = YahooChartProvider().snapshot("TEST")

    assert snapshot.symbol == "TEST"
    assert snapshot.price == 105.0
    assert snapshot.previous_close == 100.0
    assert snapshot.volume == 1600.0
    assert snapshot.average_volume == 1000.0
    assert snapshot.high == 106.0
    assert snapshot.low == 99.0
    assert snapshot.observed_at == datetime.fromtimestamp(1_700_000_000, tz=timezone.utc)
    assert snapshot.source == "yahoo_chart"


def test_provider_rejects_missing_price(monkeypatch):
    payload = {"chart": {"result": [{"meta": {"regularMarketTime": 1_700_000_000}}]}}
    monkeypatch.setattr("iea.providers.market.requests.get", lambda *args, **kwargs: FakeResponse(payload))

    with pytest.raises(ValueError, match="market price missing"):
        YahooChartProvider().snapshot("TEST")


def test_provider_rejects_missing_timestamp(monkeypatch):
    payload = {"chart": {"result": [{"meta": {"regularMarketPrice": 105.0}}]}}
    monkeypatch.setattr("iea.providers.market.requests.get", lambda *args, **kwargs: FakeResponse(payload))

    with pytest.raises(ValueError, match="market timestamp missing"):
        YahooChartProvider().snapshot("TEST")


def test_configured_symbols(monkeypatch):
    monkeypatch.setenv("IEA_MARKET_SYMBOLS", "TEST, BTC-USD, , GC=F")
    assert configured_symbols() == ["TEST", "BTC-USD", "GC=F"]
