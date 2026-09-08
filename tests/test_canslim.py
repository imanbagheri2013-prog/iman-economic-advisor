from iea.canslim import CanSlimInput, analyze_canslim


def test_canslim_does_not_invent_missing_fundamentals():
    result = analyze_canslim("TEST", CanSlimInput())
    assert result["action"] == "WAIT"
    assert set(result["missing_criteria"]) >= {"C", "A", "N", "S", "L", "I", "M"}


def test_canslim_candidate_requires_complete_strong_inputs():
    result = analyze_canslim(
        "TEST",
        CanSlimInput(
            current_eps_growth_pct=30,
            annual_eps_growth_pct=25,
            new_catalyst=True,
            price_near_high=True,
            demand_score=80,
            leader_score=90,
            institutional_sponsorship_score=75,
            market_trend_score=80,
        ),
    )
    assert result["action"] == "CANSLIM_CANDIDATE"
    assert result["score"] == 100.0
    assert result["missing_criteria"] == []
