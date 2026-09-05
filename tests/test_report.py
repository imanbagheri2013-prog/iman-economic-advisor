from iea.report import advisor_report


def test_advisor_report_renders_unified_result():
    result = {
        "engine": "iea_equity_advisor_v1",
        "symbol": "TEST",
        "analysis": {
            "final_score": 98.4,
            "final_signal": "ATTRACTIVE",
            "reasons": ["strong margins", "material upside to intrinsic value"],
        },
        "market": {
            "score": 70,
            "coverage": 1.0,
            "regime": "RISK_ON",
        },
        "decision": {
            "action": "BUY_BIAS",
            "risk_tier": "LOW",
            "conviction": "HIGH",
        },
        "combined_score": 81.36,
        "weights": {"equity": 0.4, "market": 0.6},
    }

    rendered = advisor_report(result)

    assert "# IEA Advisor Report — TEST" in rendered
    assert "Combined score: **81.36**" in rendered
    assert "Equity signal: **ATTRACTIVE**" in rendered
    assert "Market regime: **RISK_ON**" in rendered
    assert "Action: **BUY_BIAS**" in rendered
    assert "strong margins" in rendered


def test_advisor_report_accepts_missing_optional_sections():
    rendered = advisor_report({"symbol": "TEST"})

    assert "# IEA Advisor Report — TEST" in rendered
    assert "Combined score: **N/A**" in rendered
    assert "Action: **N/A**" in rendered
