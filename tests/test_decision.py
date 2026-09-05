from iea.decision import build_decision


def _safe_factors():
    return [
        {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
        {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
    ]


def test_insufficient_coverage_is_no_trade_with_low_risk_budget():
    result = build_decision(
        {
            "score": 80,
            "coverage": 0.5,
            "regime": "RISK_ON",
            "factors": _safe_factors(),
        }
    )
    assert result["action"] == "NO_TRADE"
    assert result["risk_tier"] == "LOW"
    assert result["exposure_multiplier"] == 1.0
    assert "no material risk flags" in result["risk_rationale"]
    assert "100%" in result["exposure_rationale"]


def test_risk_on_decisive_score_is_buy_bias():
    result = build_decision(
        {
            "score": 80,
            "coverage": 0.8,
            "regime": "RISK_ON",
            "factors": _safe_factors(),
        }
    )
    assert result["action"] == "BUY_BIAS"
    assert result["risk_tier"] == "LOW"
    assert result["exposure_multiplier"] == 1.0


def test_risk_off_decisive_score_is_sell_bias():
    result = build_decision(
        {
            "score": 20,
            "coverage": 0.8,
            "regime": "RISK_OFF",
            "factors": _safe_factors(),
        }
    )
    assert result["action"] == "SELL_BIAS"
    assert result["risk_tier"] == "LOW"
    assert result["risk_multiplier"] == 1.0
    assert result["exposure_multiplier"] == 1.0


def test_neutral_score_is_hold():
    result = build_decision(
        {
            "score": 50,
            "coverage": 0.8,
            "regime": "NEUTRAL",
            "factors": _safe_factors(),
        }
    )
    assert result["action"] == "HOLD"
    assert result["risk_tier"] == "LOW"
    assert result["exposure_multiplier"] == 1.0


def test_high_news_risk_blocks_trade_and_sets_critical_budget():
    result = build_decision(
        {
            "score": 80,
            "coverage": 1.0,
            "regime": "RISK_ON",
            "factors": [
                {"name": "news_risk", "details": {"risk_regime": "HIGH_RISK"}},
                {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
            ],
        }
    )
    assert result["action"] == "NO_TRADE"
    assert result["risk_score"] == 60
    assert result["risk_tier"] == "CRITICAL"
    assert result["risk_multiplier"] == 0.4
    assert result["exposure_multiplier"] == 0.0
    assert "high_news_risk" in result["risk_rationale"]
    assert "0%" in result["exposure_rationale"]


def test_liquidity_unavailable_blocks_trade_and_sets_high_budget():
    result = build_decision(
        {
            "score": 80,
            "coverage": 1.0,
            "regime": "RISK_ON",
            "factors": [
                {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
            ],
        }
    )
    assert result["action"] == "NO_TRADE"
    assert result["risk_score"] == 50
    assert result["risk_tier"] == "HIGH"
    assert result["risk_multiplier"] == 0.5
    assert result["exposure_multiplier"] == 0.5
    assert "liquidity_unavailable" in result["risk_rationale"]
    assert "50%" in result["exposure_rationale"]


def test_extreme_funding_reduces_conviction_and_sets_moderate_budget():
    result = build_decision(
        {
            "score": 80,
            "coverage": 1.0,
            "regime": "RISK_ON",
            "factors": [
                {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
                {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
                {"name": "funding_rate", "details": {"funding_rate_pct": 0.1}},
            ],
        }
    )
    assert result["action"] == "BUY_BIAS"
    assert result["risk_score"] == 25
    assert result["risk_tier"] == "MODERATE"
    assert result["risk_multiplier"] == 0.75
    assert result["exposure_multiplier"] == 0.75
    assert result["conviction"] < 1.0
    assert "extreme_funding_crowding" in result["risk_rationale"]
    assert "75%" in result["exposure_rationale"]


def test_oi_trend_divergence_adds_risk_and_sets_moderate_budget():
    result = build_decision(
        {
            "score": 80,
            "coverage": 1.0,
            "regime": "RISK_ON",
            "factors": [
                {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
                {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
                {"name": "open_interest", "details": {"oi_change_pct_1h": 6.0}},
                {"name": "trend", "details": {"return_4h_pct": -2.0}},
            ],
        }
    )
    assert result["action"] == "BUY_BIAS"
    assert result["risk_score"] == 20
    assert result["risk_tier"] == "MODERATE"
    assert result["risk_multiplier"] == 0.8
    assert result["exposure_multiplier"] == 0.75
    assert "oi_trend_divergence" in result["risk_flags"]
    assert "oi_trend_divergence" in result["risk_rationale"]
