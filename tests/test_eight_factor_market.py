from dataclasses import dataclass

import pytest
import requests

from iea.eight_factor import _dynamic_confidence, analyze_eight_factor
from iea.intelligence_v2 import FactorResult
from iea.market_adapters import MarketSnapshot, ResilientMarketAdapter


@dataclass
class FakeMarket:
    symbol: str = "BTCUSDT"
    funding_rate: float = 0.0001
    snapshot_calls: int = 0
    provider: str = "BINANCE_FUTURES"

    def snapshot(self):
        self.snapshot_calls += 1
        return MarketSnapshot(symbol=self.symbol, price=100000.0, change_pct=2.0, volume=1000.0, quote_volume=100000000.0, bid=99999.0, ask=100001.0, open_interest=50000.0, funding_rate=self.funding_rate, oi_change_pct=1.0, oi_previous=49505.0, return_4h_pct=1.5, return_24h_pct=2.5, relative_volume=1.8, bid_depth=2_000_000.0, ask_depth=1_800_000.0, depth_imbalance=0.0526315789)


@dataclass
class FailingMarket:
    symbol: str = "BTCUSDT"
    snapshot_calls: int = 0

    def snapshot(self):
        self.snapshot_calls += 1
        response = requests.Response()
        response.status_code = 451
        response.url = "https://fapi.binance.com/fapi/v1/ticker/24hr?symbol=BTCUSDT"
        raise requests.HTTPError("451 Client Error: Unavailable For Legal Reasons", response=response)


@dataclass
class FailingPrimary:
    symbol: str = "BTCUSDT"
    timeout: float = 10.0
    provider: str = "BINANCE_FUTURES"
    snapshot_calls: int = 0

    def snapshot(self):
        self.snapshot_calls += 1
        raise requests.HTTPError("451 Client Error")


@dataclass
class FakeSecondary:
    symbol: str = "BTCUSDT"
    timeout: float = 10.0
    provider: str = "BYBIT_LINEAR"
    snapshot_calls: int = 0

    def snapshot(self):
        self.snapshot_calls += 1
        return FakeMarket(provider=self.provider).snapshot()


@dataclass
class FakeSentiment:
    value: float = 62.0
    classification: str = "Greed"

    def snapshot(self):
        return {"value": self.value, "classification": self.classification, "previous_value": 69.0, "change": -7.0, "timestamp": "2026-09-02T00:00:00+00:00"}


def test_eight_factor_market_adapters_fill_six_factors(tmp_path):
    from iea.storage import Store
    store = Store(tmp_path / "eight.sqlite3")
    market = FakeMarket()
    try:
        report = analyze_eight_factor(store, market, FakeSentiment())
        assert report["symbol"] == "BTCUSDT"
        assert report["coverage"] == 0.75
        assert report["score"] is not None
        assert report["regime"] in {"RISK_ON", "NEUTRAL", "RISK_OFF"}
        assert market.snapshot_calls == 1
        by_name = {item["name"]: item for item in report["factors"]}
        for name in ("trend", "volume", "liquidity", "open_interest", "funding_rate", "sentiment"):
            assert by_name[name]["status"] == "OK"
        assert by_name["trend"]["details"]["return_4h_pct"] == 1.5
        assert by_name["trend"]["details"]["return_24h_pct"] == 2.5
        assert by_name["volume"]["details"]["relative_volume_1h"] == 1.8
        assert by_name["liquidity"]["details"]["bid_depth_usd"] == 2_000_000.0
        assert by_name["liquidity"]["details"]["ask_depth_usd"] == 1_800_000.0
        assert by_name["liquidity"]["details"]["depth_imbalance"] == 0.0526
        assert by_name["open_interest"]["details"]["open_interest"] == 50000.0
        assert by_name["open_interest"]["details"]["previous_open_interest"] == 49505.0
        assert by_name["open_interest"]["details"]["oi_change_pct_1h"] == 1.0
        assert by_name["funding_rate"]["details"]["funding_rate_pct"] == 0.01
        assert by_name["funding_rate"]["details"]["funding_regime"] == "LONG_CROWDED"
        assert by_name["funding_rate"]["score"] == 46.67
        assert by_name["sentiment"]["details"]["value"] == 62.0
        assert by_name["sentiment"]["details"]["classification"] == "Greed"
        assert by_name["sentiment"]["details"]["change_1d"] == -7.0
        assert by_name["fundamental"]["status"] == "UNAVAILABLE"
        assert by_name["news_risk"]["status"] == "UNAVAILABLE"
    finally:
        store.close()


def test_eight_factor_capital_flows_into_advisory_sizing(tmp_path):
    from iea.storage import Store
    store = Store(tmp_path / "capital.sqlite3")
    try:
        report = analyze_eight_factor(store, FakeMarket(), FakeSentiment(), capital=100000000)
        assert report["decision"]["exposure_budget"] == 100000000.0
        assert report["decision"]["exposure_multiplier"] == 1.0
    finally:
        store.close()


def test_market_confidence_uses_sample_depth():
    full = FactorResult(
        "trend",
        "OK",
        70.0,
        provider="BINANCE_FUTURES",
        details={"return_4h_pct": 1.0, "return_24h_pct": 2.0, "sample_count": 25},
    )
    partial = FactorResult(
        "trend",
        "OK",
        70.0,
        provider="BINANCE_FUTURES",
        details={"return_4h_pct": 1.0, "return_24h_pct": 2.0, "sample_count": 5},
    )
    assert _dynamic_confidence(full) == 0.993
    assert _dynamic_confidence(partial) < _dynamic_confidence(full)


def test_eight_factor_market_provider_failure_is_non_fatal(tmp_path):
    from iea.storage import Store
    store = Store(tmp_path / "provider_failure.sqlite3")
    market = FailingMarket()
    try:
        report = analyze_eight_factor(store, market, FakeSentiment())
        assert market.snapshot_calls == 1
        by_name = {item["name"]: item for item in report["factors"]}
        for name in ("trend", "volume", "liquidity", "open_interest", "funding_rate"):
            assert by_name[name]["status"] == "UNAVAILABLE"
            assert by_name[name]["provider"] == "BINANCE_FUTURES"
            assert by_name[name]["details"]["error_type"] == "HTTPError"
            assert by_name[name]["details"]["status_code"] == 451
        assert by_name["sentiment"]["status"] == "OK"
    finally:
        store.close()


def test_resilient_market_adapter_falls_back_to_secondary():
    primary = FailingPrimary()
    secondary = FakeSecondary()
    adapter = ResilientMarketAdapter(primary=primary, secondary=secondary)
    snapshot = adapter.snapshot()
    assert snapshot.symbol == "BTCUSDT"
    assert primary.snapshot_calls == 1
    assert secondary.snapshot_calls == 1
    assert adapter.provider == "BYBIT_LINEAR"


@pytest.mark.parametrize(
    ("funding_rate", "expected_score", "expected_regime"),
    [(0.0, 50.0, "NEUTRAL"), (0.0006, 16.0, "EXTREME_LONG"), (-0.0006, 84.0, "EXTREME_SHORT")],
)
def test_funding_rate_crowding_extremes(tmp_path, funding_rate, expected_score, expected_regime):
    from iea.storage import Store
    store = Store(tmp_path / "funding.sqlite3")
    try:
        report = analyze_eight_factor(store, FakeMarket(funding_rate=funding_rate), FakeSentiment())
        funding = next(item for item in report["factors"] if item["name"] == "funding_rate")
        assert funding["score"] == expected_score
        assert funding["details"]["funding_regime"] == expected_regime
    finally:
        store.close()
