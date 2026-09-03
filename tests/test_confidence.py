from datetime import datetime, timedelta, timezone

from iea.confidence import clamp_confidence, combine_confidence, coverage_confidence, freshness_confidence, sample_confidence


def test_clamp_confidence_bounds_values():
    assert clamp_confidence(-1.0) == 0.0
    assert clamp_confidence(0.4) == 0.4
    assert clamp_confidence(2.0) == 1.0


def test_freshness_confidence_decays_with_age():
    now = datetime.now(timezone.utc)
    assert freshness_confidence(now.isoformat(), max_age_hours=24) == 1.0
    halfway = (now - timedelta(hours=12)).isoformat()
    assert 0.49 <= freshness_confidence(halfway, max_age_hours=24) <= 0.51
    old = (now - timedelta(hours=48)).isoformat()
    assert freshness_confidence(old, max_age_hours=24) == 0.0


def test_freshness_confidence_fails_closed_for_invalid_timestamp():
    assert freshness_confidence("not-a-timestamp", max_age_hours=24) == 0.0


def test_coverage_and_sample_confidence():
    assert coverage_confidence(0.75) == 0.75
    assert coverage_confidence("bad") == 0.0
    assert sample_confidence(12, target=24) == 0.5
    assert sample_confidence(48, target=24) == 1.0


def test_combine_confidence_is_conservative():
    assert combine_confidence(1.0, 1.0) == 1.0
    assert combine_confidence(0.25, 1.0) == 0.5
    assert combine_confidence(0.0, 1.0) == 0.0
