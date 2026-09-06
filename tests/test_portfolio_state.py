from iea.portfolio_state import build_portfolio_state, normalize_positions
from iea.storage import Store


def test_portfolio_state_scales_with_runtime_capital_and_tracks_pnl():
    state = build_portfolio_state(
        100_000_000,
        cash=70_000_000,
        positions=[
            {"quantity": 100, "entry_price": 100_000, "stop_loss": 90_000, "current_price": 105_000}
        ],
        realized_pnl=1_000_000,
        unrealized_pnl=500_000,
    )
    assert state["capital"] == 100_000_000
    assert state["position_count"] == 1
    assert state["current_exposure"] == 10_500_000
    assert state["current_risk"] == 1_000_000
    assert state["realized_pnl"] == 1_000_000
    assert state["unrealized_pnl"] == 500_000
    assert state["drawdown"] == 0.0
    assert state["scaling_mode"] == "DYNAMIC_PERCENTAGE_BASED"


def test_portfolio_state_uses_peak_equity_for_drawdown():
    state = build_portfolio_state(
        100_000_000,
        cash=60_000_000,
        positions=[{"market_value": 30_000_000}],
        peak_equity=100_000_000,
    )
    assert state["equity"] == 90_000_000
    assert state["drawdown"] == 10_000_000
    assert state["drawdown_ratio"] == 0.1


def test_normalize_positions_ignores_non_dicts():
    positions = normalize_positions([{"quantity": 2}, None, "bad"])
    assert len(positions) == 1
    assert positions[0]["quantity"] == 2.0


def test_store_persists_latest_portfolio_snapshot(tmp_path):
    store = Store(tmp_path / "iea.db")
    state = build_portfolio_state(100_000_000, cash=80_000_000, positions=[])
    store.save_portfolio_snapshot(state)
    assert store.count_portfolio_snapshots() == 1
    latest = store.latest_portfolio_snapshot()
    assert latest["capital"] == 100_000_000
    assert latest["cash"] == 80_000_000
    store.close()
