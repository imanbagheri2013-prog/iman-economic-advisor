from iea.live_decision import apply_live_market_overlay


def base_decision(action="BUY_BIAS"):
    return {"action": action, "conviction": 0.8, "risk_flags": []}


def test_not_configured_live_data_does_not_change_existing_decision():
    result = apply_live_market_overlay(base_decision(), {"status": "NOT_CONFIGURED"}, symbol="AAPL")
    assert result["action"] == "BUY_BIAS"


def test_matching_stale_signal_fails_closed():
    result = apply_live_market_overlay(
        base_decision(),
        {"status": "OK", "signals": [{"symbol": "AAPL", "action": "BUY", "data_fresh": False}]},
        symbol="AAPL",
    )
    assert result["action"] == "NO_TRADE"
    assert result["conviction"] == 0.0
    assert "live_market_data_stale" in result["risk_flags"]


def test_matching_same_side_live_signal_validates_decision():
    result = apply_live_market_overlay(
        base_decision(),
        {"status": "OK", "signals": [{"symbol": "AAPL", "action": "BUY", "data_fresh": True}]},
        symbol="AAPL",
    )
    assert result["action"] == "BUY_BIAS"
    assert result["live_market_validated"] is True
    assert result["live_market_signal"] == "BUY"


def test_disagreeing_live_signal_fails_closed():
    result = apply_live_market_overlay(
        base_decision(),
        {"status": "OK", "signals": [{"symbol": "AAPL", "action": "SELL", "data_fresh": True}]},
        symbol="AAPL",
    )
    assert result["action"] == "NO_TRADE"
    assert result["conviction"] == 0.0
    assert "live_market_signal_disagrees" in result["risk_flags"]


def test_non_actionable_live_signal_blocks_action_for_matching_symbol():
    result = apply_live_market_overlay(
        base_decision(),
        {"status": "OK", "signals": [{"symbol": "AAPL", "action": "WAIT", "data_fresh": True}]},
        symbol="AAPL",
    )
    assert result["action"] == "NO_TRADE"
    assert "live_market_signal_not_actionable" in result["risk_flags"]
