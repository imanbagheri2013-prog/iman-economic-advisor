from iea.capital_flow import CapitalObservation, central_bank_watchlist, score_capital_observations


def test_capital_observations_detect_accumulation_and_reduction():
    observations = [
        CapitalObservation(
            institution="Central Bank A",
            institution_type="central_bank",
            country="X",
            asset="gold",
            action="purchase",
            confidence=1.0,
            reason="reserve diversification",
        ),
        CapitalObservation(
            institution="Fund B",
            institution_type="sovereign_wealth_fund",
            country="Y",
            asset="gold",
            action="buy",
            confidence=0.8,
            reason="inflation hedge",
        ),
        CapitalObservation(
            institution="Bank C",
            institution_type="commercial_bank",
            country="Z",
            asset="government_bonds",
            action="sell",
            confidence=1.0,
        ),
    ]

    signals = score_capital_observations(observations)
    by_asset = {signal.asset: signal for signal in signals}

    assert by_asset["GOLD"].direction == "ACCUMULATION"
    assert by_asset["GOLD"].score == 1.8
    assert by_asset["GOVERNMENT_BONDS"].direction == "REDUCTION"


def test_capital_observation_confidence_is_validated():
    observation = CapitalObservation(
        institution="Test",
        institution_type="central_bank",
        country="X",
        asset="gold",
        action="buy",
        confidence=1.2,
    )
    try:
        score_capital_observations([observation])
    except ValueError as exc:
        assert "confidence" in str(exc)
    else:
        raise AssertionError("invalid confidence should raise ValueError")


def test_watchlist_contains_major_global_and_iranian_central_banks():
    watchlist = central_bank_watchlist()
    assert "Federal Reserve" in watchlist
    assert "European Central Bank" in watchlist
    assert "People's Bank of China" in watchlist
    assert "Central Bank of the Republic of Iran" in watchlist
