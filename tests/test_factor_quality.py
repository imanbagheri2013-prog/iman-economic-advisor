from iea.intelligence_v2 import FactorResult, data_quality_summary


def test_data_quality_excludes_not_applicable_factors_from_coverage():
    results = [
        FactorResult("fundamental", "OK", score=60, confidence=0.9, provider="FRED"),
        FactorResult("trend", "OK", score=55, confidence=0.8, provider="TSETMC_CDN"),
        FactorResult("volume", "OK", score=50, confidence=0.7, provider="TSETMC_CDN"),
        FactorResult("liquidity", "OK", score=52, confidence=0.8, provider="TSETMC_CDN"),
        FactorResult("sentiment", "OK", score=48, confidence=0.8, provider="ALTERNATIVE_ME"),
        FactorResult("news_risk", "OK", score=45, confidence=0.75, provider="GDELT"),
        FactorResult("open_interest", "UNAVAILABLE", details={"reason": "not_applicable_to_cash_equities"}),
        FactorResult("funding_rate", "UNAVAILABLE", details={"reason": "not_applicable_to_cash_equities"}),
    ]

    quality = data_quality_summary(results)

    assert quality["factor_count"] == 8
    assert quality["applicable_factor_count"] == 6
    assert quality["usable_factor_count"] == 6
    assert quality["not_applicable_count"] == 2
    assert quality["usable_coverage"] == 1.0
    assert quality["status"] == "GOOD"
    assert quality["score"] > 0


def test_data_quality_marks_missing_factor_as_degraded():
    results = [
        FactorResult("fundamental", "OK", score=60, confidence=0.9),
        FactorResult("trend", "UNAVAILABLE", details={"reason": "provider_error"}),
        FactorResult("volume", "OK", score=50, confidence=0.8),
        FactorResult("liquidity", "OK", score=52, confidence=0.8),
        FactorResult("sentiment", "OK", score=48, confidence=0.8),
        FactorResult("news_risk", "OK", score=45, confidence=0.75),
        FactorResult("open_interest", "UNAVAILABLE", details={"reason": "not_applicable_to_cash_equities"}),
        FactorResult("funding_rate", "UNAVAILABLE", details={"reason": "not_applicable_to_cash_equities"}),
    ]

    quality = data_quality_summary(results)

    assert quality["applicable_factor_count"] == 6
    assert quality["usable_factor_count"] == 5
    assert quality["not_applicable_count"] == 2
    assert quality["usable_coverage"] == round(5 / 6, 3)
    assert quality["status"] == "DEGRADED"

    trend = next(item for item in quality["factors"] if item["name"] == "trend")
    assert trend["quality_status"] == "UNAVAILABLE"
    assert trend["usable"] is False
    assert trend["not_applicable"] is False
