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
    assert report == {
        "score": None,
        "regime": "INSUFFICIENT_DATA",
        "coverage": 0.125,
        "available_factors": ["fundamental"],
        "unavailable_factors": list(FACTOR_NAMES[1:]),
    }


def test_aggregate_with_full_coverage():
    results = [FactorResult(name, "OK", 75.0) for name in FACTOR_NAMES]
    report = aggregate(results)
    assert report == {
        "score": 75.0,
        "regime": "RISK_ON",
        "coverage": 1.0,
        "available_factors": list(FACTOR_NAMES),
        "unavailable_factors": [],
    }
