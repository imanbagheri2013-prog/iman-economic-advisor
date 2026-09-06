from __future__ import annotations

import json

import pytest

from iea.central_bank_provider import fetch_observations, parse_payload


def test_parse_cbi_json_contract():
    payload = json.dumps(
        {
            "observations": [
                {
                    "indicator": "liquidity_m2",
                    "value": 123.4,
                    "unit": "IRR bn",
                    "observed_at": "2026-08-31",
                    "frequency": "monthly",
                }
            ]
        }
    )
    result = parse_payload(payload, "application/json")
    assert len(result) == 1
    assert result[0].indicator == "liquidity_m2"
    assert result[0].value == 123.4


def test_parse_cbi_csv_contract():
    payload = "indicator,value,unit,observed_at,frequency\nmonetary_base,10,IRR bn,2026-08-31,monthly\n"
    result = parse_payload(payload, "text/csv")
    assert result[0].indicator == "monetary_base"
    assert result[0].frequency == "monthly"


def test_parse_rejects_missing_required_columns():
    with pytest.raises(ValueError, match="indicator,value,observed_at"):
        parse_payload("indicator,value\nliquidity_m2,10\n", "text/csv")


def test_fetch_returns_empty_when_source_is_not_configured(monkeypatch):
    monkeypatch.delenv("IEA_CBI_DATA_URL", raising=False)
    assert fetch_observations() == []


def test_fetch_rejects_future_observation(monkeypatch):
    class Response:
        headers = {"content-type": "application/json"}
        text = json.dumps(
            {
                "observations": [
                    {
                        "indicator": "m1",
                        "value": 1,
                        "unit": "IRR",
                        "observed_at": "2999-01-01",
                    }
                ]
            }
        )

        def raise_for_status(self):
            return None

    monkeypatch.setattr("iea.central_bank_provider.requests.get", lambda *args, **kwargs: Response())
    with pytest.raises(ValueError, match="future"):
        fetch_observations("https://example.test/cbi.json")
