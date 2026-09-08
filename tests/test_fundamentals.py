from iea.fundamentals import parse_financials


def test_parse_financials_calculates_core_ratios():
    payload = [{
        "revenue": 1000,
        "gross_profit": 300,
        "operating_profit": 180,
        "net_income": 120,
        "assets": 1500,
        "liabilities": 600,
        "equity": 900,
        "current_assets": 500,
        "current_liabilities": 250,
        "operating_cash_flow": 160,
        "capex": 40,
    }]
    result = parse_financials(payload)
    assert result["status"] == "READY"
    assert result["ratios"]["gross_margin_pct"] == 30.0
    assert result["ratios"]["operating_margin_pct"] == 18.0
    assert result["ratios"]["net_margin_pct"] == 12.0
    assert result["ratios"]["debt_to_equity"] == 600 / 900
    assert result["ratios"]["current_ratio"] == 2.0
    assert result["ratios"]["roe_pct"] == 120 / 900 * 100
    assert result["ratios"]["roa_pct"] == 120 / 1500 * 100
    assert result["ratios"]["free_cash_flow"] == 120
    assert result["ratios"]["free_cash_flow_margin_pct"] == 12.0
    assert result["ratios"]["operating_cash_flow_to_net_income"] == 160 / 120


def test_parse_financials_calculates_sequential_growth():
    payload = [
        {"period": "2026 Q2", "revenue": 1200, "eps": 30, "net_income": 180},
        {"period": "2025 Q2", "revenue": 1000, "eps": 20, "net_income": 120},
    ]
    result = parse_financials(payload)
    assert result["growth"]["revenue_growth_pct"] == 20.0
    assert result["growth"]["eps_growth_pct"] == 50.0
    assert result["growth"]["net_income_growth_pct"] == 50.0


def test_parse_financials_calculates_explicit_annual_growth():
    payload = [
        {"period": "2026 annual 12 months", "revenue": 1500, "eps": 40, "net_income": 240},
        {"period": "2025 annual 12 months", "revenue": 1200, "eps": 30, "net_income": 180},
    ]
    result = parse_financials(payload)
    assert result["growth"]["annual_revenue_growth_pct"] == 25.0
    assert result["growth"]["annual_eps_growth_pct"] == (40 / 30 - 1) * 100
    assert result["growth"]["annual_net_income_growth_pct"] == (240 / 180 - 1) * 100


def test_parse_financials_never_invents_missing_values():
    result = parse_financials([{"revenue": 1000}])
    assert result["status"] == "READY"
    assert result["ratios"]["net_margin_pct"] is None
    assert result["ratios"]["roe_pct"] is None
    assert result["ratios"]["free_cash_flow"] is None
    assert result["growth"]["eps_growth_pct"] is None
