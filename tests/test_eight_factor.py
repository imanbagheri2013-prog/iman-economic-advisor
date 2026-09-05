from datetime import datetime, timezone

from iea.intelligence_v2 import FACTOR_NAMES, FactorRegistry, FactorResult, aggregate


def test_registry_exposes_all_eight_factors():
    results = FactorRegistry().evaluate(None)
    assert tuple(result.name for result in results) == FACTOR_NAMES
    assert all(result.status == "UNAVAILABLE" for result in results)


def test_registry_rejects_unknown_factor():
    registry = FactorRegistry()
    try:
        registry.register("unknown", lambda _: FactorResult("unknown", "OK", 50.0))
    except ValueError as exc:
        assert "Unknown factor" in str(exc)
    else:
        raise AssertionError("unknown factor was accepted")


def test_aggregate_requires_minimum_coverage():
    results = [
        FactorResult("fundamental", "OK", 70.0, timestamp=datetime.now(timezone.utc).isoformat()),
        *[FactorResult(name, "UNAVAILABLE") for name in FACTOR_NAMES[1:]],
    ]
    report = aggregate(results)
    assert report["score"] is None
    assert report["regime"] == "INSUFFICIENT_DATA"
    assert report["coverage"] == 0.125
    assert report["available_factors"] == ["fundamental"]
    assert report["unavailable_factors"] == list(FACTOR_NAMES[1:])
    assert report["data_quality"]["score"] == 12.5
    assert report["data_quality"]["status"] == "DEGRADED"
    assert report["data_quality"]["usable_factor_count"] == 1
    assert report["data_quality"]["not_applicable_count"] == 0


def test_aggregate_with_full_coverage():
    results = [FactorResult(name, "OK", 75.0) for name in FACTOR_NAMES]
    report = aggregate(results)
    assert report["score"] == 75.0
    assert report["regime"] == "RISK_ON"
    assert report["factor_weights"] == {name: 0.125 for name in FACTOR_NAMES}
    assert report["factor_contributions"] == {name: 9.38 for name in FACTOR_NAMES}
    assert report["coverage"] == 1.0
    assert report["available_factors"] == list(FACTOR_NAMES)
    assert report["unavailable_factors"] == []
    assert report["data_quality"]["score"] == 100.0
    assert report["data_quality"]["status"] == "GOOD"
    assert report["data_quality"]["usable_factor_count"] == 8
    assert report["data_quality"]["applicable_factor_count"] == 8


def test_aggregate_weights_scores_by_confidence():
    results = [
        FactorResult("fundamental", "OK", 100.0, confidence=1.0),
        FactorResult("trend", "OK", 0.0, confidence=0.25),
        *[FactorResult(name, "UNAVAILABLE") for name in FACTOR_NAMES[2:]],
    ]
    report = aggregate(results, minimum_coverage=0.25)
    assert report["score"] == 80.0
    assert report["regime"] == "RISK_ON"
    assert report["factor_weights"] == {"fundamental": 0.8, "trend": 0.2}
    assert report["factor_contributions"] == {"fundamental": 80.0, "trend": 0.0}


def test_aggregate_clamps_invalid_confidence_safely():
    results = [
        FactorResult("fundamental", "OK", 100.0, confidence=2.0),
        FactorResult("trend", "OK", 0.0, confidence=-1.0),
        *[FactorResult(name, "UNAVAILABLE") for name in FACTOR_NAMES[2:]],
    ]
    report = aggregate(results, minimum_coverage=0.25)
    assert report["score"] == 100.0
    assert report["factor_weights"] == {"fundamental": 1.0, "trend": 0.0}


def test_aggregate_explainability_preserves_factor_order():
    results = [
        FactorResult("fundamental", "OK", 60.0, confidence=0.5),
        FactorResult("trend", "OK", 40.0, confidence=0.5),
        *[FactorResult(name, "UNAVAILABLE") for name in FACTOR_NAMES[2:]],
    ]
    report = aggregate(results, minimum_coverage=0.25)
    assert list(report["factor_weights"]) == ["fundamental", "trend"]
    assert list(report["factor_contributions"]) == ["fundamental", "trend"]
