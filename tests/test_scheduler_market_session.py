from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from iea import scheduler


TEHRAN = ZoneInfo("Asia/Tehran")


def test_scheduler_market_context_uses_tehran_session():
    assert scheduler._market_context(datetime(2026, 9, 5, 10, 0, tzinfo=TEHRAN)) == ("OPEN", "2026-09-05")
    assert scheduler._market_context(datetime(2026, 9, 5, 8, 50, tzinfo=TEHRAN)) == ("PRE_OPEN", "2026-09-05")
    assert scheduler._market_context(datetime(2026, 9, 5, 13, 0, tzinfo=TEHRAN)) == ("CLOSED", "2026-09-05")
    assert scheduler._market_context(datetime(2026, 9, 3, 10, 0, tzinfo=TEHRAN)) == ("CLOSED", "2026-09-03")


def test_closed_scheduler_reuses_last_valid_state(tmp_path: Path, monkeypatch):
    state_path = tmp_path / "iran_market_state.json"
    state_path.write_text(
        '{"generated_at":"2026-09-05T06:30:00+00:00","score":72.5,"regime":"RISK_ON",'
        '"decision":{"action":"BUY_BIAS"},"market_status":"OPEN","stale":false}',
        encoding="utf-8",
    )
    monkeypatch.setattr(scheduler, "MARKET_STATE_PATH", state_path)

    result = scheduler._closed_market_intelligence("CLOSED", "2026-09-05")

    assert result["score"] == 72.5
    assert result["regime"] == "RISK_ON"
    assert result["decision"]["action"] == "BUY_BIAS"
    assert result["market_status"] == "CLOSED"
    assert result["data_mode"] == "LAST_VALID_OPEN_SNAPSHOT"
    assert result["stale"] is True
    assert result["last_valid_market_snapshot_at"] == "2026-09-05T06:30:00+00:00"


def test_closed_scheduler_has_safe_no_state_fallback(tmp_path: Path, monkeypatch):
    monkeypatch.setattr(scheduler, "MARKET_STATE_PATH", tmp_path / "missing.json")

    result = scheduler._closed_market_intelligence("PRE_OPEN", "2026-09-05")

    assert result["market_status"] == "PRE_OPEN"
    assert result["data_mode"] == "NO_LIVE_MARKET_DATA"
    assert result["stale"] is True
    assert result["decision"]["action"] == "NO_TRADE"
    assert result["score"] is None
