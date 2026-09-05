from iea.eight_factor import analyze_eight_factor
from iea.storage import Store


def test_eight_factor_capital_flows_into_advisory_sizing(tmp_path):
    from tests.test_eight_factor_market import FakeMarket, FakeSentiment

    store = Store(tmp_path / "capital.sqlite3")
    try:
        report = analyze_eight_factor(
            store, FakeMarket(), FakeSentiment(), capital=100000000
        )
        assert report["decision"]["exposure_budget"] == 75000000.0
        assert report["decision"]["exposure_multiplier"] == 0.75
    finally:
        store.close()
