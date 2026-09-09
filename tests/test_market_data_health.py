from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, patch

from iea.market_data_health import check_market_mirror_health


def _response(payload):
    response = Mock()
    response.raise_for_status.return_value = None
    response.json.return_value = payload
    return response


def _payload(generated_at=None, symbols=None):
    return {
        "generated_at": generated_at or datetime.now(timezone.utc).isoformat(),
        "market_status": "OPEN",
        "symbols": symbols or {
            "فولاد": {"instrument": {"lVal18AFC": "فولاد"}, "instrument_info": {"pClosing": 100.0, "priceYesterday": 99.0, "quoteStatus": "ACTIVE"}},
            "فملی": {"instrument": {"lVal18AFC": "فملی"}, "instrument_info": {"pClosing": 200.0, "priceYesterday": 198.0, "quoteStatus": "ACTIVE"}},
            "وبملت": {"instrument": {"lVal18AFC": "وبملت"}, "instrument_info": {"pClosing": 300.0, "priceYesterday": 300.0, "quoteStatus": "SUSPENDED_OR_NO_TRADE"}},
        },
    }


def test_market_mirror_health_checks_freshness_coverage_and_analysis_ready_symbols():
    payload = _payload()
    with patch("iea.market_data_health.requests.get", return_value=_response(payload)):
        result = check_market_mirror_health("https://example.test/market.json", ["فولاد", "فملی", "وبملت"])

    assert result["status"] == "HEALTHY"
    assert result["mirror_reachable"] is True
    assert result["coverage"] == 1.0
    assert result["valid_symbol_count"] == 3
    assert result["analysis_ready_symbol_count"] == 2
    assert result["analysis_ready_symbols"] == ["فولاد", "فملی"]
    assert result["suspended_symbols"] == ["وبملت"]
    assert result["missing_required_data"] == []


def test_market_mirror_health_blocks_stale_open_snapshot():
    generated_at = (datetime.now(timezone.utc) - timedelta(minutes=31)).isoformat()
    with patch("iea.market_data_health.requests.get", return_value=_response(_payload(generated_at=generated_at))):
        result = check_market_mirror_health("https://example.test/market.json", ["فولاد", "فملی"])

    assert result["status"] == "CRITICAL"
    assert any("stale" in error for error in result["errors"])


def test_market_mirror_health_detects_missing_required_price_data():
    symbols = _payload()["symbols"]
    symbols["فملی"]["instrument_info"]["pClosing"] = None
    with patch("iea.market_data_health.requests.get", return_value=_response(_payload(symbols=symbols))):
        result = check_market_mirror_health("https://example.test/market.json", ["فولاد", "فملی"])

    assert result["status"] == "HEALTHY"
    assert result["analysis_ready_symbol_count"] == 1
    assert {item["symbol"] for item in result["missing_required_data"]} == {"فملی"}
    assert result["missing_required_data"][0]["fields"] == ["price"]


def test_market_mirror_health_returns_critical_when_no_analysis_ready_symbols():
    symbols = _payload()["symbols"]
    for row in symbols.values():
        row["instrument_info"]["pClosing"] = None
    with patch("iea.market_data_health.requests.get", return_value=_response(_payload(symbols=symbols))):
        result = check_market_mirror_health("https://example.test/market.json", ["فولاد", "فملی"])

    assert result["status"] == "CRITICAL"
    assert result["analysis_ready_symbol_count"] == 0
