from iea.valuation import valuation_diagnostics


def test_valuation_diagnostics_cover_multiple_multiples_and_sector_comparison():
    result = valuation_diagnostics({
        "pe": 6,
        "forwardPE": 5,
        "pb": 0.8,
        "ps": 1.2,
        "evEbitda": 4,
        "evSales": 1.0,
        "sectorPE": 10,
        "sectorPB": 1.0,
        "sectorPS": 1.5,
        "sectorEbitda": 5,
        "sectorEVSales": 1.25,
        "dividendYield": 4.5,
        "historicalPEPercentile": 20,
    })
    assert result["pe"] == 6.0
    assert result["forward_pe"] == 5.0
    assert result["pb"] == 0.8
    assert result["ev_ebitda"] == 4.0
    assert result["dividend_yield_pct"] == 4.5
    assert result["pe_vs_sector"] == 0.6
    assert result["pe_discount_pct"] == 40.0
    assert result["relative"]["pb"]["ratio"] == 0.8
    assert result["historical_pe_status"] == "lower_than_history"
    assert "pe_discount_to_sector" in result["flags"]


def test_valuation_diagnostics_fail_closed_when_peer_or_historical_data_is_missing():
    result = valuation_diagnostics({"pe": 8, "pb": 1.1})
    assert result["relative"]["pe"]["status"] == "unavailable"
    assert result["relative"]["pb"]["status"] == "unavailable"
    assert result["historical_pe_percentile"] is None
    assert result["historical_pe_status"] == "unavailable"
    assert "pe_sector_comparison_unavailable" in result["flags"]
