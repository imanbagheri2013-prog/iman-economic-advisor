from iea.decision import build_decision


def test_decision_blocks_when_coverage_is_insufficient():
    report = {"score": 80.0, "coverage": 0.5, "regime": "RISK_ON"}
    decision = build_decision(report)
    assert decision["action"] == "NO_TRADE"
    assert decision["conviction"] == 0.0
    assert decision["risk_tier"] == "LOW"
    assert decision["risk_multiplier"] == 1.0


def test_decision_returns_buy_bias_for_decisive_risk_on():
    report = {"score": 80.0, "coverage": 1.0, "regime": "RISK_ON"}
    decision = build_decision(report)
    assert decision["action"] == "BUY_BIAS"
    assert decision["conviction"] > 0.5
    assert decision["risk_tier"] == "LOW"


def test_decision_returns_sell_bias_for_decisive_risk_off():
    report = {"score": 20.0, "coverage": 0.75, "regime": "RISK_OFF"}
    decision = build_decision(report)
    assert decision["action"] == "SELL_BIAS"
    assert decision["conviction"] > 0.5
    assert decision["risk_multiplier"] == 1.0


def test_decision_holds_neutral_regime():
    report = {"score": 50.0, "coverage": 1.0, "regime": "NEUTRAL"}
    decision = build_decision(report)
    assert decision["action"] == "HOLD"
    assert decision["conviction"] == 0.5


def test_high_news_risk_blocks_directional_decision():
    report = {
        "score": 85.0,
        "coverage": 1.0,
        "regime": "RISK_ON",
        "factors": [
            {"name": "news_risk", "status": "OK", "details": {"risk_regime": "HIGH_RISK"}},
        ],
    }
    decision = build_decision(report)
    assert decision["action"] == "NO_TRADE"
    assert decision["conviction"] == 0.0
    assert decision["risk_score"] == 60
    assert decision["risk_tier"] == "CRITICAL"
    assert decision["risk_multiplier"] == 0.4
    assert "high_news_risk" in decision["risk_flags"]


def test_liquidity_unavailable_blocks_directional_decision():
    report = {
        "score": 85.0,
        "coverage": 1.0,
        "regime": "RISK_ON",
        "factors": [
            {"name": "liquidity", "status": "UNAVAILABLE", "details": {}},
        ],
    }
    decision = build_decision(report)
    assert decision["action"] == "NO_TRADE"
    assert decision["risk_score"] == 50
    assert decision["risk_tier"] == "HIGH"
    assert decision["risk_multiplier"] == 0.5
    assert "liquidity_unavailable" in decision["risk_flags"]


def test_extreme_funding_reduces_conviction():
    report = {
        "score": 80.0,
        "coverage": 1.0,
        "regime": "RISK_ON",
        "factors": [
            {"name": "funding_rate", "status": "OK", "details": {"funding_rate_pct": 0.10}},
        ],
    }
    decision = build_decision(report)
    assert decision["action"] == "BUY_BIAS"
    assert decision["conviction"] < 0.75
    assert decision["risk_score"] == 25
    assert decision["risk_tier"] == "MODERATE"
    assert decision["risk_multiplier"] == 0.75
    assert "extreme_funding_crowding" in decision["risk_flags"]


def test_oi_trend_divergence_adds_risk_flag():
    report = {
        "score": 80.0,
        "coverage": 1.0,
        "regime": "RISK_ON",
        "factors": [
            {"name": "open_interest", "status": "OK", "details": {"oi_change_pct_1h": 6.0}},
            {"name": "trend", "status": "OK", "details": {"return_4h_pct": -2.0}},
        ],
    }
    decision = build_decision(report)
    assert decision["action"] == "BUY_BIAS"
    assert decision["risk_score"] == 20
    assert decision["risk_tier"] == "MODERATE"
    assert decision["risk_multiplier"] == 0.8
    assert "oi_trend_divergence" in decision["risk_flags"]
