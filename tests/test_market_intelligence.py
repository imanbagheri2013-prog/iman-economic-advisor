from datetime import datetime, timedelta, timezone

from iea.market_intelligence import MarketSnapshot, analyze_snapshot, analyze_snapshots


def fresh_snapshot(**overrides):
    data = {
        "symbol": "TEST",
        "observed_at": datetime.now(timezone.utc),
        "price": 110.0,
        "previous_close": 100.0,
        "source": "test",
    }
    data.update(overrides)
    return MarketSnapshot(**data)


def test_fresh_positive_snapshot_can_be_actionable():
    signal = analyze_snapshot(fresh_snapshot())
    assert signal.action == "BUY"
    assert signal.data_fresh is True
    assert signal.score > 0


def test_stale_snapshot_can_never_be_actionable():
    signal = analyze_snapshot(
        fresh_snapshot(observed_at=datetime.now(timezone.utc) - timedelta(hours=2))
    )
    assert signal.action == "NO_TRADE"
    assert signal.market_state == "STALE"
    assert signal.confidence == 0
    assert signal.data_fresh is False
    assert signal.entry_price is None
    assert signal.stop_loss is None
    assert signal.take_profit is None


def test_missing_previous_close_is_no_trade():
    signal = analyze_snapshot(fresh_snapshot(previous_close=None))
    assert signal.action == "NO_TRADE"
    assert signal.market_state == "INSUFFICIENT_DATA"


def test_volume_and_range_contribute_to_score():
    signal = analyze_snapshot(
        fresh_snapshot(
            volume=2_000,
            average_volume=1_000,
            high=112,
            low=95,
        )
    )
    assert signal.score > 0
    assert any("volume_ratio" in reason for reason in signal.reasons)


def test_actionable_buy_signal_exposes_two_risk_levels():
    signal = analyze_snapshot(fresh_snapshot(price=110.0, previous_close=100.0, low=105.0))
    assert signal.action == "BUY"
    assert signal.entry_price == 110.0
    assert signal.stop_loss == 105.0
    assert signal.take_profit == 120.0
    assert signal.risk_reward == 2.0


def test_actionable_sell_signal_exposes_two_risk_levels():
    signal = analyze_snapshot(fresh_snapshot(price=90.0, previous_close=100.0, high=95.0))
    assert signal.action == "SELL"
    assert signal.entry_price == 90.0
    assert signal.stop_loss == 95.0
    assert signal.take_profit == 80.0
    assert signal.risk_reward == 2.0


def test_closed_market_signal_has_advisory_levels_but_no_live_action():
    signal = analyze_snapshot(
        fresh_snapshot(
            price=110.0,
            previous_close=100.0,
            market_status="CLOSED",
            observed_at=datetime.now(timezone.utc) - timedelta(hours=1),
            low=105.0,
        )
    )
    assert signal.action == "NO_TRADE"
    assert signal.analysis_action == "BUY"
    assert signal.entry_price == 110.0
    assert signal.stop_loss == 105.0
    assert signal.take_profit == 120.0
    assert signal.risk_reward == 2.0


def test_batch_analysis_exposes_safety_contract():
    report = analyze_snapshots(
        [
            fresh_snapshot(symbol="A"),
            fresh_snapshot(
                symbol="B",
                observed_at=datetime.now(timezone.utc) - timedelta(hours=2),
            ),
        ]
    )
    assert report["count"] == 2
    assert report["actionable_count"] == 1
    assert report["safety"]["stale_data_action"] == "NO_TRADE"
    assert report["safety"]["risk_levels_action"] == "ADVISORY_ONLY"
