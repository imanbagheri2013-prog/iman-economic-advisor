from iea.canslim import CanSlimInput, analyze_canslim


def test_canslim_does_not_invent_missing_fundamentals():
    result = analyze_canslim("TEST", CanSlimInput())
    assert result["action"] == "WAIT"
    assert set(result["missing_criteria"]) >= {"C", "A", "N", "S", "L", "I", "M"}
    assert result["fundamental_score"] is None
    assert result["fundamental_quality_score"] is None
    assert result["fundamental_confidence_pct"] == 0.0
    assert result["fundamental_score_complete"] is False


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


def test_fundamental_score_is_weighted_and_complete_when_all_metrics_exist():
    result = analyze_canslim(
        "TEST",
        CanSlimInput(
            revenue_growth_pct=20,
            gross_margin_pct=30,
            operating_margin_pct=15,
            net_margin_pct=12,
            roe_pct=20,
            roic_pct=15,
            current_ratio=1.5,
            debt_to_equity=1.0,
            free_cash_flow=100,
            operating_cash_flow=150,
        ),
    )
    assert result["fundamental_score"] == 100.0
    assert result["fundamental_quality_score"] == 100.0
    assert result["fundamental_score_coverage_pct"] == 100.0
    assert result["fundamental_confidence_pct"] == 100.0
    assert result["fundamental_score_complete"] is True
    assert result["fundamental_missing_metrics"] == []


def test_fundamental_score_is_discounted_by_low_coverage():
    result = analyze_canslim("TEST", CanSlimInput(roe_pct=20, roic_pct=12))
    assert result["fundamental_quality_score"] == 100.0
    assert result["fundamental_score"] == 26.09
    assert result["fundamental_score_coverage_pct"] == 26.09
    assert result["fundamental_confidence_pct"] == 26.09
    assert result["fundamental_score_complete"] is False
    assert "revenue_growth_pct" in result["fundamental_missing_metrics"]


def test_valuation_diagnostics_compare_pe_with_sector_without_inventing_values():
    result = analyze_canslim("TEST", CanSlimInput(pe=6.0, sector_pe=10.0))
    assert result["valuation_diagnostics"]["pe_vs_sector"] == 0.6
    assert result["valuation_diagnostics"]["pe_discount_pct"] == 40.0
    assert "pe_discount_to_sector" in result["valuation_diagnostics"]["flags"]
