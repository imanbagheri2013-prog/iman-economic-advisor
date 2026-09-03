from iea.decision import build_decision


def test_decision_blocks_when_coverage_is_insufficient():
    report = {"score": 80.0, "coverage": 0.5, "regime": "RISK_ON"}
    decision = build_decision(report)
    assert decision["action"] == "NO_TRADE"
    assert decision["conviction"] == 0.0


def test_decision_returns_buy_bias_for_decisive_risk_on():
    report = {"score": 80.0, "coverage": 1.0, "regime": "RISK_ON"}
    decision = build_decision(report)
    assert decision["action"] == "BUY_BIAS"
    assert decision["conviction"] > 0.5


def test_decision_returns_sell_bias_for_decisive_risk_off():
    report = {"score": 20.0, "coverage": 0.75, "regime": "RISK_OFF"}
    decision = build_decision(report)
    assert decision["action"] == "SELL_BIAS"
    assert decision["conviction"] > 0.5


def test_decision_holds_neutral_regime():
    report = {"score": 50.0, "coverage": 1.0, "regime": "NEUTRAL"}
    decision = build_decision(report)
    assert decision["action"] == "HOLD"
    assert decision["conviction"] == 0.5
