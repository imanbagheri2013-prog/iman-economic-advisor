from iea.central_bank import (
    MONETARY_INDICATORS,
    PolicyEvent,
    build_monetary_dashboard,
    classify_monetary_impulse,
    growth_rate,
    normalize_observation,
    summarize_policy_event,
)


def test_normalize_cbi_observation_validates_and_normalizes_indicator():
    observation = normalize_observation(
        "LIQUIDITY_M2",
        100.0,
        "IRR_bn",
        "2026-09-01",
        frequency="monthly",
    )
    assert observation.indicator == "liquidity_m2"
    assert observation.value == 100.0
    assert observation.source == "CBI"


def test_unknown_cbi_indicator_is_rejected():
    try:
        normalize_observation("bitcoin_price", 1.0, "USD", "2026-09-01")
    except ValueError as exc:
        assert "Unknown CBI monetary indicator" in str(exc)
    else:
        raise AssertionError("unknown indicator was accepted")


def test_growth_rate_handles_zero_base():
    assert growth_rate(110, 100) == 10.0
    assert growth_rate(100, 0) is None


def test_dashboard_tracks_latest_observation_and_missing_indicators():
    observations = [
        normalize_observation("liquidity_m2", 100, "IRR_bn", "2026-08-01"),
        normalize_observation("liquidity_m2", 110, "IRR_bn", "2026-09-01"),
        normalize_observation("monetary_base", 50, "IRR_bn", "2026-09-01", revision=True),
    ]
    dashboard = build_monetary_dashboard(observations)
    assert dashboard["indicator_count"] == 2
    assert dashboard["indicators"]["liquidity_m2"]["value"] == 110.0
    assert dashboard["revision_count"] == 1
    assert "monetary_base" not in dashboard["missing_indicators"]
    assert len(dashboard["missing_indicators"]) == len(MONETARY_INDICATORS) - 2


def test_monetary_impulse_classification_is_transparent():
    result = classify_monetary_impulse(
        monetary_base_growth=35,
        liquidity_growth=32,
        bank_credit_growth=25,
    )
    assert result["status"] == "OK"
    assert result["direction"] == "STRONG_EXPANSION"
    assert result["score"] == 33.5


def test_monetary_impulse_requires_data():
    result = classify_monetary_impulse(monetary_base_growth=None, liquidity_growth=None)
    assert result == {"status": "INSUFFICIENT_DATA", "direction": "UNKNOWN", "score": None}


def test_policy_event_is_normalized_for_advisor():
    event = PolicyEvent(
        event_type="liquidity_injection",
        announced_at="2026-09-01T10:00:00+03:30",
        title="Test liquidity operation",
        direction="EXPANSIONARY",
        magnitude=1000,
        unit="IRR_bn",
    )
    result = summarize_policy_event(event)
    assert result["event_type"] == "liquidity_injection"
    assert result["direction"] == "EXPANSIONARY"
    assert result["magnitude"] == 1000
