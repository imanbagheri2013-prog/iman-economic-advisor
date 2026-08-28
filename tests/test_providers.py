from datetime import datetime

import pytest
import requests

from iea.providers.fred import FRED
from iea.providers.bls import BLS


class FakeResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(
                f"HTTP {self.status_code}"
            )

    def json(self):
        return self._payload


def test_fred_observations(monkeypatch):
    def fake_get(*args, **kwargs):
        return FakeResponse(
            {
                "observations": [
                    {
                        "date": "2026-01-01",
                        "value": "123.45",
                    },
                    {
                        "date": "2026-02-01",
                        "value": ".",
                    },
                ]
            }
        )

    monkeypatch.setattr(
        "iea.providers.fred.requests.get",
        fake_get,
    )

    provider = FRED(api_key="test-key")

    observations = provider.observations(
        "TEST_SERIES",
        limit=100,
    )

    assert len(observations) == 2

    first = observations[0]

    assert first.provider == "fred"
    assert first.series_id == "TEST_SERIES"
    assert first.value == 123.45
    assert first.status == "OK"
    assert first.date == datetime.fromisoformat(
        "2026-01-01T00:00:00+00:00"
    )

    second = observations[1]

    assert second.value is None
    assert second.status == "MISSING"


def test_fred_requires_api_key(monkeypatch):
    monkeypatch.delenv("FRED_API_KEY", raising=False)

    with pytest.raises(RuntimeError, match="FRED_API_KEY is not set"):
        FRED()


def test_fred_http_error(monkeypatch):
    def fake_get(*args, **kwargs):
        return FakeResponse(
            {"error": "bad request"},
            status_code=400,
        )

    monkeypatch.setattr(
        "iea.providers.fred.requests.get",
        fake_get,
    )

    provider = FRED(api_key="test-key")

    with pytest.raises(requests.HTTPError):
        provider.observations("TEST_SERIES")


def test_bls_observations(monkeypatch):
    def fake_post(*args, **kwargs):
        return FakeResponse(
            {
                "Results": {
                    "series": [
                        {
                            "seriesID": "TEST_BLS",
                            "data": [
                                {
                                    "year": "2026",
                                    "period": "M01",
                                    "value": "1,234.50",
                                },
                                {
                                    "year": "2026",
                                    "period": "M02",
                                    "value": "567.25",
                                },
                            ],
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr(
        "iea.providers.bls.requests.post",
        fake_post,
    )

    provider = BLS(api_key="test-key")

    observations = provider.observations(
        "TEST_BLS",
        2026,
        2026,
    )

    assert len(observations) == 2

    first = observations[0]

    assert first.provider == "bls"
    assert first.series_id == "TEST_BLS"
    assert first.value == 1234.50
    assert first.status == "OK"
    assert first.date == datetime.fromisoformat(
        "2026-01-01T00:00:00+00:00"
    )

    second = observations[1]

    assert second.value == 567.25
    assert second.status == "OK"
    assert second.date == datetime.fromisoformat(
        "2026-02-01T00:00:00+00:00"
    )


def test_bls_invalid_value(monkeypatch):
    def fake_post(*args, **kwargs):
        return FakeResponse(
            {
                "Results": {
                    "series": [
                        {
                            "seriesID": "TEST_BLS",
                            "data": [
                                {
                                    "year": "2026",
                                    "period": "M01",
                                    "value": "not-a-number",
                                }
                            ],
                        }
                    ]
                }
            }
        )

    monkeypatch.setattr(
        "iea.providers.bls.requests.post",
        fake_post,
    )

    provider = BLS()

    observations = provider.observations(
        "TEST_BLS",
        2026,
        2026,
    )

    assert len(observations) == 1
    assert observations[0].value is None
    assert observations[0].status == "MISSING"


def test_bls_http_error(monkeypatch):
    def fake_post(*args, **kwargs):
        return FakeResponse(
            {"error": "bad request"},
            status_code=400,
        )

    monkeypatch.setattr(
        "iea.providers.bls.requests.post",
        fake_post,
    )

    provider = BLS()

    with pytest.raises(requests.HTTPError):
        provider.observations(
            "TEST_BLS",
            2026,
            2026,
        )
