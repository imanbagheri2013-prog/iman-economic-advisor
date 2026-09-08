from datetime import datetime, timedelta, timezone

from iea.market_intelligence import MarketSnapshot, analyze_snapshot


def test_closed_snapshot_is_analyzable_but_not_actionable():
    snapshot = MarketSnapshot(
        symbol="TEST",
        observed_at=datetime.now(timezone.utc) - timedelta(hours=2),
        price=110,
        previous_close=100,
        source="tsetmc",
        market_status="CLOSED",
        data_date="20260907",
    )
    signal = analyze_snapshot(snapshot)
    assert signal.analysis_action == "BUY"
    assert signal.action == "NO_TRADE"
    assert signal.market_status == "CLOSED"
    assert signal.data_date == "20260907"
    assert signal.data_fresh is False
