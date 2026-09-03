from iea.eight_factor import _dynamic_confidence
from iea.intelligence_v2 import FactorResult


def test_dynamic_confidence_rewards_complete_fresh_data():
    result = FactorResult(
        "trend",
        "OK",
        70.0,
        confidence=0.1,
        provider="BINANCE_FUTURES",
        timestamp="2099-01-01T00:00:00+00:00",
        details={"return_4h_pct": 1.0, "return_24h_pct": 2.0},
    )
    confidence = _dynamic_confidence(result)
    assert 0.97 <= confidence <= 0.98


def test_dynamic_confidence_penalizes_missing_market_fields():
    result = FactorResult(
        "liquidity",
        "OK",
        60.0,
        provider="BINANCE_FUTURES",
        details={"bid_depth_usd": 1000.0, "ask_depth_usd": None, "depth_imbalance": 0.1},
    )
    confidence = _dynamic_confidence(result)
    assert 0.70 <= confidence < 0.98


def test_dynamic_confidence_uses_news_sample_size():
    result = FactorResult(
        "news_risk",
        "OK",
        80.0,
        provider="GDELT",
        timestamp="2099-01-01T00:00:00+00:00",
        details={"article_count": 20},
    )
    confidence = _dynamic_confidence(result)
    assert 0.79 <= confidence <= 0.81


def test_dynamic_confidence_zero_for_unavailable_factor():
    result = FactorResult("trend", "UNAVAILABLE", provider="BINANCE_FUTURES")
    assert _dynamic_confidence(result) == 0.0
