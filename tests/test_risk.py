from iea.risk import DEFAULT_RISK_POLICY, RiskPolicy


def test_default_risk_policy_preserves_exposure_bands():
    policy = DEFAULT_RISK_POLICY
    assert policy.tier(0) == "LOW"
    assert policy.tier(20) == "MODERATE"
    assert policy.tier(40) == "HIGH"
    assert policy.tier(60) == "CRITICAL"
    assert policy.exposure_multiplier("LOW") == 1.0
    assert policy.exposure_multiplier("MODERATE") == 0.75
    assert policy.exposure_multiplier("HIGH") == 0.5
    assert policy.exposure_multiplier("CRITICAL") == 0.0


def test_risk_policy_can_be_tuned_without_changing_decision_code():
    policy = RiskPolicy(moderate_score=30, moderate_exposure=0.6)
    assert policy.tier(20) == "LOW"
    assert policy.tier(30) == "MODERATE"
    assert policy.exposure_multiplier("MODERATE") == 0.6


def test_risk_policy_is_immutable():
    try:
        DEFAULT_RISK_POLICY.moderate_exposure = 0.5
    except (AttributeError, TypeError):
        pass
    else:
        raise AssertionError("RiskPolicy must remain immutable")
