from iea.providers.fred import FRED


class FakeResponse:
    def __init__(self, status_code, payload=None, headers=None):
        self.status_code = status_code
        self._payload = payload or {}
        self.headers = headers or {}

    def raise_for_status(self):
        if self.status_code >= 400:
            import requests
            raise requests.HTTPError(f"status={self.status_code}")

    def json(self):
        return self._payload


def test_fred_retries_rate_limit(monkeypatch):
    calls = []
    responses = [
        FakeResponse(429, headers={"Retry-After": "0"}),
        FakeResponse(200, {"observations": [{"date": "2026-09-01", "value": "12.5"}]}),
    ]

    monkeypatch.setattr("iea.providers.fred.requests.get", lambda *args, **kwargs: calls.append(1) or responses.pop(0))
    monkeypatch.setattr("iea.providers.fred.time.sleep", lambda *_: None)

    result = FRED(api_key="test").observations("TEST")
    assert len(calls) == 2
    assert result[0].value == 12.5


def test_fred_raises_after_max_retries(monkeypatch):
    calls = []
    monkeypatch.setattr(
        "iea.providers.fred.requests.get",
        lambda *args, **kwargs: calls.append(1) or FakeResponse(429, headers={"Retry-After": "0"}),
    )
    monkeypatch.setattr("iea.providers.fred.time.sleep", lambda *_: None)

    import pytest
    with pytest.raises(Exception):
        FRED(api_key="test").observations("TEST")
    assert len(calls) == 3
