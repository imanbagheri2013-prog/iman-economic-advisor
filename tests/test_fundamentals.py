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
    assert result["ratios"]["free_cash_flow"] == 120


def test_parse_financials_never_invents_missing_values():
    result = parse_financials([{"revenue": 1000}])
    assert result["status"] == "READY"
    assert result["ratios"]["net_margin_pct"] is None
    assert result["ratios"]["roe_pct"] is None
    assert result["ratios"]["free_cash_flow"] is None
