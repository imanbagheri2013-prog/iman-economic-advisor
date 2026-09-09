from iea.capital_allocation import build_capital_allocation


def _ready_decision():
    return {
        "action": "BUY_BIAS",
        "final_action": "BUY",
        "conviction": 0.8,
        "portfolio": {"capital": 100_000_000.0},
        "exposure_budget": 80_000_000.0,
        "position_size": 30_000_000.0,
        "trade_levels": {
            "entry_price": 100_000.0,
            "stop_loss": 95_000.0,
            "take_profit": 110_000.0,
        },
    }


def test_buy_final_action_produces_ready_capital_allocation():
    decision, allocation = build_capital_allocation(_ready_decision())
    assert allocation["status"] == "READY"
    assert allocation["action"] == "BUY"
    assert allocation["capital"] == 100_000_000.0
    assert allocation["exposure_budget"] == 80_000_000.0
    assert allocation["position_size"] == 30_000_000.0
    assert allocation["trade_levels"]["take_profit"] == 110_000.0
    assert allocation["execution"] == "NONE"
    assert decision["capital_allocation_status"] == "READY"


def test_sell_final_action_produces_ready_capital_allocation():
    source = _ready_decision()
    source["action"] = "SELL_BIAS"
    source["final_action"] = "SELL"
    decision, allocation = build_capital_allocation(source)
    assert allocation["status"] == "READY"
    assert allocation["action"] == "SELL"
    assert allocation["position_size"] == 30_000_000.0
    assert decision["capital_allocation_policy"] == "FINAL_ACTION_RISK_CAPITAL_ALIGNED"


def test_no_trade_always_zeroes_capital_allocation():
    source = _ready_decision()
    source["action"] = "NO_TRADE"
    source["final_action"] = "NO_TRADE"
    decision, allocation = build_capital_allocation(source)
    assert allocation["status"] == "BLOCKED"
    assert allocation["action"] == "NO_TRADE"
    assert allocation["exposure_budget"] == 0.0
    assert allocation["position_size"] == 0.0
    assert allocation["trade_levels"] is None
    assert decision["exposure_budget"] == 0.0
    assert decision["position_size"] == 0.0


def test_missing_capital_or_levels_blocks_final_action():
    source = _ready_decision()
    source["portfolio"] = {"capital": 0.0}
    decision, allocation = build_capital_allocation(source)
    assert allocation["status"] == "BLOCKED"
    assert allocation["action"] == "NO_TRADE"
    assert "capital_allocation_unavailable" in decision["risk_flags"]
    assert decision["final_action"] == "NO_TRADE"
    assert decision["position_size"] == 0.0


def test_final_gate_blocked_decision_cannot_retain_sizing():
    source = _ready_decision()
    source["final_action"] = "NO_TRADE"
    source["action"] = "NO_TRADE"
    source["risk_flags"] = ["market_data_health_blocked"]
    decision, allocation = build_capital_allocation(source)
    assert allocation["status"] == "BLOCKED"
    assert allocation["exposure_budget"] == 0.0
    assert allocation["position_size"] == 0.0
    assert decision["risk_flags"] == ["market_data_health_blocked"]
