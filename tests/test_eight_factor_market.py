from dataclasses import dataclass

from iea.eight_factor import analyze_eight_factor
from iea.market_adapters import MarketSnapshot


@dataclass
class FakeMarket:
    symbol: str = "BTCUSDT"

    def snapshot(self):
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
        )


def test_eight_factor_market_adapters_fill_five_crypto_factors(tmp_path):
    from iea.storage import Store

    store = Store(tmp_path / "eight.sqlite3")
    try:
        report = analyze_eight_factor(store, FakeMarket())
        assert report["symbol"] == "BTCUSDT"
        assert report["coverage"] == 0.75
        assert report["score"] is not None
        assert report["regime"] in {"RISK_ON", "NEUTRAL", "RISK_OFF"}
        by_name = {item["name"]: item for item in report["factors"]}
        for name in ("trend", "volume", "liquidity", "open_interest", "funding_rate"):
            assert by_name[name]["status"] == "OK"
        assert by_name["sentiment"]["status"] == "UNAVAILABLE"
        assert by_name["news_risk"]["status"] == "UNAVAILABLE"
    finally:
        store.close()
