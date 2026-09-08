from iea.api import _composite_score, _flow_composite


def test_flow_composite_is_directional_and_observed_only():
    assert _flow_composite({"real_net_value": 10, "legal_net_value": -5}) == 50.0
    assert _flow_composite({}) is None


def test_composite_score_uses_only_available_components():
    result = _composite_score({"fundamental_quality_score": 80, "score": 70}, {"real_net_value": 10})
    assert result["score"] == 76.25
    assert result["coverage_pct"] == 80.0
    assert result["complete"] is False
    assert result["missing_components"] == ["money_flow"]


def test_composite_score_complete_when_all_components_exist():
    result = _composite_score({"fundamental_quality_score": 80, "score": 70}, {"real_net_value": 10, "legal_net_value": 10})
    assert result["score"] == 76.0
    assert result["coverage_pct"] == 100.0
    assert result["complete"] is True
