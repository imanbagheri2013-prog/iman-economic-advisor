from datetime import datetime, timezone

from iea.central_bank import (
    MONETARY_INDICATORS,
    PolicyEvent,
    build_monetary_dashboard,
    build_monetary_policy_index,
    classify_monetary_impulse,
    growth_rate,
    normalize_observation,
    observation_freshness,
    summarize_policy_event,
)
from iea.central_bank_provider import fetch_observations


def test_normalize_cbi_observation_validates_and_normalizes_indicator():
    observation = normalize_observation("LIQUIDITY_M2", 100.0, "IRR_bn", "2026-09-01", frequency="monthly")
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


def test_observation_freshness_uses_frequency_specific_window():
    now = datetime(2026, 9, 6, tzinfo=timezone.utc)
    monthly = normalize_observation(
        "liquidity_m2", 100, "IRR_bn", "2026-07-25T00:00:00+00:00", frequency="monthly"
    )
    daily = normalize_observation(
        "monetary_base", 100, "IRR_bn", "2026-09-04T00:00:00+00:00", frequency="daily"
    )
    assert observation_freshness(monthly, now=now)["fresh"] is True
    assert observation_freshness(daily, now=now)["fresh"] is True


def test_dashboard_exposes_cbi_freshness_counts():
    now = datetime(2026, 9, 6, tzinfo=timezone.utc)
    observations = [
        normalize_observation("liquidity_m2", 100, "IRR_bn", "2026-09-01", frequency="monthly"),
        normalize_observation("monetary_base", 50, "IRR_bn", "2026-08-20", frequency="daily"),
    ]
    dashboard = build_monetary_dashboard(observations, now=now)
    assert dashboard["freshness"]["fresh_indicator_count"] == 1
    assert dashboard["freshness"]["stale_indicator_count"] == 1


def test_monetary_impulse_classification_is_transparent():
    result = classify_monetary_impulse(monetary_base_growth=35, liquidity_growth=32, bank_credit_growth=25)
    assert result["status"] == "OK"
    assert result["direction"] == "STRONG_EXPANSION"
    assert result["score"] == 33.5


def test_monetary_impulse_requires_data():
    result = classify_monetary_impulse(monetary_base_growth=None, liquidity_growth=None)
    assert result == {"status": "INSUFFICIENT_DATA", "direction": "UNKNOWN", "score": None}


def test_monetary_policy_index_is_transparent_and_bounded():
    result = build_monetary_policy_index(
        monetary_base_growth=30,
        liquidity_growth=25,
        bank_credit_growth=20,
        policy_rate_change=-2,
        reserve_requirement_change=-1,
        net_open_market_operation=5,
    )
    assert result["status"] == "OK"
    assert result["direction"] == "EXPANSIONARY"
    assert -100 <= result["score"] <= 100
    assert result["coverage"] > 0.8


def test_monetary_policy_index_requires_data():
    assert build_monetary_policy_index()["status"] == "INSUFFICIENT_DATA"


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


def test_cbi_provider_uses_fallback_after_primary_failure(monkeypatch):
    class Response:
        def __init__(self, text, status=200):
            self.text = text
            self.status = status
            self.headers = {"content-type": "text/csv"}

        def raise_for_status(self):
            if self.status >= 400:
                raise RuntimeError("upstream failure")

    calls = []

    def fake_get(url, timeout):
        calls.append(url)
        if url == "https://official.example/cbi.csv":
            return Response("", status=503)
        return Response("indicator,value,observed_at\nliquidity_m2,100,2026-09-01")

    monkeypatch.setattr("iea.central_bank_provider.requests.get", fake_get)
    monkeypatch.setenv("IEA_CBI_DATA_URL", "https://official.example/cbi.csv")
    monkeypatch.setenv("IEA_CBI_FALLBACK_URLS", "https://fallback.example/cbi.csv")

    observations = fetch_observations()
    assert observations[0].indicator == "liquidity_m2"
    assert calls == ["https://official.example/cbi.csv", "https://fallback.example/cbi.csv"]
