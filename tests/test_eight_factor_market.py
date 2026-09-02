from dataclasses import dataclass

from iea.eight_factor import analyze_eight_factor
from iea.market_adapters import MarketSnapshot


@dataclass
class FakeMarket:
    symbol: str = "BTCUSDT"
    snapshot_calls: int = 0

    def snapshot(self):
        self.snapshot_calls += 1
        return MarketSnapshot(
            symbol=self.symbol,
            price=100000.0,
            change_pct=2.0,
            volume=1000.0,
            quote_volume=100000000.0,
            bid=99999.0,
            ask=100001.0,
            open_interest=50000.0,
            funding_rate=0.0001,
            oi_change_pct=1.0,
            return_4h_pct=1.5,
            return_24h_pct=2.5,
            relative_volume=1.8,
            bid_depth=2_000_000.0,
            ask_depth=1_800_000.0,
            depth_imbalance=0.0526315789,
        )


def test_eight_factor_market_adapters_fill_five_crypto_factors(tmp_path):
    from iea.storage import Store

    store = Store(tmp_path / "eight.sqlite3")
    market = FakeMarket()
    try:
        report = analyze_eight_factor(store, market)
        assert report["symbol"] == "BTCUSDT"
        assert report["coverage"] == 0.625
        assert report["score"] is not None
        assert report["regime"] in {"RISK_ON", "NEUTRAL", "RISK_OFF"}
        assert market.snapshot_calls == 1
        by_name = {item["name"]: item for item in report["factors"]}
        for name in ("trend", "volume", "liquidity", "open_interest", "funding_rate"):
            assert by_name[name]["status"] == "OK"
        assert by_name["trend"]["details"]["return_4h_pct"] == 1.5
        assert by_name["trend"]["details"]["return_24h_pct"] == 2.5
        assert by_name["volume"]["details"]["relative_volume_1h"] == 1.8
        assert by_name["liquidity"]["details"]["bid_depth_usd"] == 2_000_000.0
        assert by_name["liquidity"]["details"]["ask_depth_usd"] == 1_800_000.0
        assert by_name["liquidity"]["details"]["depth_imbalance"] == 0.0526
        assert by_name["fundamental"]["status"] == "UNAVAILABLE"
        assert by_name["sentiment"]["status"] == "UNAVAILABLE"
        assert by_name["news_risk"]["status"] == "UNAVAILABLE"
    finally:
        store.close()
