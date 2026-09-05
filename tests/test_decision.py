from iea.decision import build_decision
from iea.risk import RiskPolicy


def _safe_factors():
    return [
        {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
        {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
    ]


def test_insufficient_coverage_is_no_trade_with_low_risk_budget():
    result = build_decision({"score": 80, "coverage": 0.5, "regime": "RISK_ON", "factors": _safe_factors()})
    assert result["action"] == "NO_TRADE"
    assert result["risk_tier"] == "LOW"
    assert result["exposure_multiplier"] == 1.0
    assert "no material risk flags" in result["risk_rationale"]
    assert "100%" in result["exposure_rationale"]


def test_risk_on_decisive_score_is_buy_bias():
    result = build_decision({"score": 80, "coverage": 0.8, "regime": "RISK_ON", "factors": _safe_factors()})
    assert result["action"] == "BUY_BIAS"
    assert result["risk_tier"] == "LOW"
    assert result["exposure_multiplier"] == 1.0


def test_risk_off_decisive_score_is_sell_bias():
    result = build_decision({"score": 20, "coverage": 0.8, "regime": "RISK_OFF", "factors": _safe_factors()})
    assert result["action"] == "SELL_BIAS"
    assert result["risk_tier"] == "LOW"
    assert result["risk_multiplier"] == 1.0
    assert result["exposure_multiplier"] == 1.0


def test_neutral_score_is_hold():
    result = build_decision({"score": 50, "coverage": 0.8, "regime": "NEUTRAL", "factors": _safe_factors()})
    assert result["action"] == "HOLD"
    assert result["risk_tier"] == "LOW"
    assert result["exposure_multiplier"] == 1.0


def test_high_news_risk_blocks_trade_and_sets_critical_budget():
    result = build_decision({"score": 80, "coverage": 1.0, "regime": "RISK_ON", "factors": [
        {"name": "news_risk", "details": {"risk_regime": "HIGH_RISK"}},
        {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
    ]})
    assert result["action"] == "NO_TRADE"
    assert result["risk_score"] == 60
    assert result["risk_tier"] == "CRITICAL"
    assert result["risk_multiplier"] == 0.4
    assert result["exposure_multiplier"] == 0.0
    assert "high_news_risk" in result["risk_rationale"]
    assert "0%" in result["exposure_rationale"]


def test_liquidity_unavailable_blocks_trade_and_sets_high_budget():
    result = build_decision({"score": 80, "coverage": 1.0, "regime": "RISK_ON", "factors": [
        {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
    ]})
    assert result["action"] == "NO_TRADE"
    assert result["risk_score"] == 50
    assert result["risk_tier"] == "HIGH"
    assert result["risk_multiplier"] == 0.5
    assert result["exposure_multiplier"] == 0.5
    assert "liquidity_unavailable" in result["risk_rationale"]
    assert "50%" in result["exposure_rationale"]


def test_extreme_funding_reduces_conviction_and_sets_moderate_budget():
    result = build_decision({"score": 80, "coverage": 1.0, "regime": "RISK_ON", "factors": [
        {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
        {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
        {"name": "funding_rate", "details": {"funding_rate_pct": 0.1}},
    ]})
    assert result["action"] == "BUY_BIAS"
    assert result["risk_score"] == 25
    assert result["risk_tier"] == "MODERATE"
    assert result["risk_multiplier"] == 0.75
    assert result["exposure_multiplier"] == 0.75
    assert result["conviction"] < 1.0
    assert "extreme_funding_crowding" in result["risk_rationale"]
    assert "75%" in result["exposure_rationale"]


def test_oi_trend_divergence_adds_risk_and_sets_moderate_budget():
    result = build_decision({"score": 80, "coverage": 1.0, "regime": "RISK_ON", "factors": [
        {"name": "news_risk", "details": {"risk_regime": "LOW_RISK"}},
        {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
        {"name": "open_interest", "details": {"oi_change_pct_1h": 6.0}},
        {"name": "trend", "details": {"return_4h_pct": -2.0}},
    ]})
    assert result["action"] == "BUY_BIAS"
    assert result["risk_score"] == 20
    assert result["risk_tier"] == "MODERATE"
    assert result["risk_multiplier"] == 0.8
    assert result["exposure_multiplier"] == 0.75
    assert "oi_trend_divergence" in result["risk_flags"]
    assert "oi_trend_divergence" in result["risk_rationale"]


def test_custom_policy_changes_decision_thresholds_without_changing_default():
    report = {"score": 68, "coverage": 0.8, "regime": "RISK_ON", "factors": _safe_factors()}
    default_result = build_decision(report)
    tuned_result = build_decision(report, RiskPolicy(buy_threshold=70.0))
    assert default_result["action"] == "BUY_BIAS"
    assert tuned_result["action"] == "HOLD"
    assert default_result["risk_tier"] == tuned_result["risk_tier"] == "LOW"


def test_capital_produces_exposure_budget_without_affecting_action():
    report = {"score": 80, "coverage": 1.0, "regime": "RISK_ON", "capital": 100000000, "factors": _safe_factors()}
    result = build_decision(report)
    assert result["action"] == "BUY_BIAS"
    assert result["exposure_multiplier"] == 1.0
    assert result["exposure_budget"] == 100000000.0
    assert "capital-based advisory budget" in result["sizing_rationale"]


def test_critical_risk_produces_zero_exposure_budget():
    report = {"score": 80, "coverage": 1.0, "regime": "RISK_ON", "capital": 100000000, "factors": [
        {"name": "news_risk", "details": {"risk_regime": "HIGH_RISK"}},
        {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
    ]}
    result = build_decision(report)
    assert result["action"] == "NO_TRADE"
    assert result["exposure_budget"] == 0.0


def test_missing_capital_keeps_decision_backward_compatible():
    result = build_decision({"score": 80, "coverage": 1.0, "regime": "RISK_ON", "factors": _safe_factors()})
    assert "exposure_budget" not in result


def test_stop_loss_position_size_is_risk_capped():
    report = {
        "score": 80,
        "coverage": 1.0,
        "regime": "RISK_ON",
        "capital": 100000000,
        "entry_price": 100000,
        "stop_loss": 95000,
        "factors": _safe_factors(),
    }
    result = build_decision(report)
    assert result["exposure_budget"] == 100000000.0
    assert result["position_size"] == 30000000.0
    assert "stop-loss distance" in result["position_sizing_rationale"]


def test_critical_risk_zeroes_stop_loss_position_size():
    report = {
        "score": 80,
        "coverage": 1.0,
        "regime": "RISK_ON",
        "capital": 100000000,
        "entry_price": 100000,
        "stop_loss": 95000,
        "factors": [
            {"name": "news_risk", "details": {"risk_regime": "HIGH_RISK"}},
            {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
        ],
    }
    result = build_decision(report)
    assert result["action"] == "NO_TRADE"
    assert result["position_size"] == 0.0


def test_buy_decision_generates_two_to_one_trade_levels():
    report = {
        "score": 80,
        "coverage": 1.0,
        "regime": "RISK_ON",
        "capital": 100000000,
        "entry_price": 100000,
        "stop_loss": 95000,
        "risk_reward_ratio": 2.0,
        "factors": _safe_factors(),
    }
    result = build_decision(report)
    assert result["action"] == "BUY_BIAS"
    assert result["trade_levels"] == {
        "entry_price": 100000.0,
        "stop_loss": 95000.0,
        "take_profit": 110000.0,
        "risk_distance": 5000.0,
        "reward_distance": 10000.0,
        "risk_reward_ratio": 2.0,
    }
    assert "risk/reward" in result["trade_levels_rationale"]


def test_sell_decision_generates_custom_risk_reward_trade_levels():
    report = {
        "score": 20,
        "coverage": 1.0,
        "regime": "RISK_OFF",
        "capital": 100000000,
        "entry_price": 100000,
        "stop_loss": 105000,
        "risk_reward_ratio": 3.0,
        "factors": _safe_factors(),
    }
    result = build_decision(report)
    assert result["action"] == "SELL_BIAS"
    assert result["trade_levels"]["take_profit"] == 85000.0
    assert result["trade_levels"]["risk_reward_ratio"] == 3.0


def test_no_trade_does_not_publish_actionable_trade_levels():
    report = {
        "score": 80,
        "coverage": 1.0,
        "regime": "RISK_ON",
        "capital": 100000000,
        "entry_price": 100000,
        "stop_loss": 95000,
        "factors": [
            {"name": "news_risk", "details": {"risk_regime": "HIGH_RISK"}},
            {"name": "liquidity", "details": {"depth_imbalance": 0.0}},
        ],
    }
    result = build_decision(report)
    assert result["action"] == "NO_TRADE"
    assert "trade_levels" not in result


def test_buy_decision_derives_dynamic_stop_loss_from_atr():
    report = {
        "score": 80,
        "coverage": 1.0,
        "regime": "RISK_ON",
        "capital": 100000000,
        "entry_price": 100000,
        "atr": 2000,
        "factors": _safe_factors(),
    }
    result = build_decision(report)
    assert result["action"] == "BUY_BIAS"
    assert result["dynamic_stop_loss"] == 97000.0
    assert result["position_size"] == 50000000.0
    assert result["trade_levels"]["take_profit"] == 106000.0
    assert "ATR" in result["dynamic_stop_loss_rationale"]


def test_sell_decision_derives_dynamic_stop_loss_from_custom_atr_multiplier():
    report = {
        "score": 20,
        "coverage": 1.0,
        "regime": "RISK_OFF",
        "capital": 100000000,
        "entry_price": 100000,
        "atr": 2000,
        "atr_multiplier": 2.0,
        "risk_reward_ratio": 3.0,
        "factors": _safe_factors(),
    }
    result = build_decision(report)
    assert result["action"] == "SELL_BIAS"
    assert result["dynamic_stop_loss"] == 104000.0
    assert result["trade_levels"]["take_profit"] == 88000.0
    assert result["trade_levels"]["risk_reward_ratio"] == 3.0


def test_explicit_stop_loss_takes_precedence_over_atr():
    report = {
        "score": 80,
        "coverage": 1.0,
        "regime": "RISK_ON",
        "capital": 100000000,
        "entry_price": 100000,
        "stop_loss": 95000,
        "atr": 2000,
        "factors": _safe_factors(),
    }
    result = build_decision(report)
    assert "dynamic_stop_loss" not in result
    assert result["trade_levels"]["stop_loss"] == 95000.0
