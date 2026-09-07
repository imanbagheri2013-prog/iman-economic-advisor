from datetime import datetime, timedelta, timezone

from iea.market_intelligence import MarketSnapshot
from iea.scheduler import _live_market_intelligence


def test_live_market_intelligence_not_configured(monkeypatch):
    monkeypatch.delenv("IEA_MARKET_SYMBOLS", raising=False)
    report = _live_market_intelligence("OPEN")
    assert report["status"] == "NOT_CONFIGURED"
    assert report["actionable_count"] == 0


def test_live_market_intelligence_isolates_provider_failures(monkeypatch):
    monkeypatch.setenv("IEA_MARKET_SYMBOLS", "GOOD,BAD")

    class FakeProvider:
        def snapshot(self, symbol):
            if symbol == "BAD":
                raise RuntimeError("provider unavailable")
            return MarketSnapshot(
                symbol="GOOD",
                observed_at=datetime.now(timezone.utc),
                price=110.0,
                previous_close=100.0,
                source="test",
            )

    monkeypatch.setattr("iea.scheduler.YahooChartProvider", FakeProvider)
    report = _live_market_intelligence("OPEN")
    assert report["status"] == "OK"
    assert report["actionable_count"] == 1
    assert report["signals"][0]["action"] == "BUY"
    assert report["errors"][0]["symbol"] == "BAD"


def test_live_market_intelligence_stale_snapshot_is_not_actionable(monkeypatch):
    monkeypatch.setenv("IEA_MARKET_SYMBOLS", "STALE")

    class FakeProvider:
        def snapshot(self, symbol):
            return MarketSnapshot(
                symbol=symbol,
                observed_at=datetime.now(timezone.utc) - timedelta(hours=2),
                price=110.0,
                previous_close=100.0,
                source="test",
            )

    monkeypatch.setattr("iea.scheduler.YahooChartProvider", FakeProvider)
    report = _live_market_intelligence("OPEN")
    assert report["status"] == "OK"
    assert report["actionable_count"] == 0
    assert report["signals"][0]["action"] == "NO_TRADE"
    assert report["signals"][0]["data_fresh"] is False
