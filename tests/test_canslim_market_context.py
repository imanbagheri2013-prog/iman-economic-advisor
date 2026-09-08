from iea.api import _canslim_market_scores


def test_canslim_market_scores_builds_s_l_i_m_from_available_data():
    result = _canslim_market_scores(
        {"return_pct": 20.0, "volume_trend_pct": 40.0},
        {"real_net_value": 100.0, "legal_net_value": 50.0},
        {"entries": [{"change": 10.0}]},
        5.0,
        8.0,
    )
    assert result["S"] > 50
    assert result["L"] > 50
    assert result["I"] > 50
    assert result["M"] > 50
    assert result["inputs"]["market_benchmark_return_pct"] == 5.0


def test_canslim_market_scores_fail_closed_without_benchmarks():
    result = _canslim_market_scores(
        {"return_pct": 20.0, "volume_trend_pct": 40.0},
        {"real_net_value": 100.0},
        {"entries": []},
        None,
        None,
    )
    assert result["S"] is not None
    assert result["L"] is None
    assert result["I"] is None
    assert result["M"] is None


def test_canslim_market_scores_do_not_invent_flow_totals():
    result = _canslim_market_scores(
        {"return_pct": 2.0},
        {},
        {"entries": []},
        None,
        None,
    )
    assert result["S"] is None
    assert result["I"] is None
