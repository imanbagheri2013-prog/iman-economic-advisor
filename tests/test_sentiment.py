from iea.sentiment import AlternativeFearGreedAdapter, sentiment_factor


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_fear_greed_adapter_parses_latest_and_previous(monkeypatch):
    payload = {
        "data": [
            {
                "value": "62",
                "value_classification": "Greed",
                "timestamp": "1788307200",
            },
            {
                "value": "69",
                "value_classification": "Greed",
                "timestamp": "1788220800",
            },
        ]
    }

    def fake_get(url, params, timeout):
        assert url == "https://api.alternative.me/fng/"
        assert params == {"limit": 2}
        assert timeout == 10.0
        return FakeResponse(payload)

    monkeypatch.setattr("iea.sentiment.requests.get", fake_get)
    snapshot = AlternativeFearGreedAdapter().snapshot()

    assert snapshot["value"] == 62.0
    assert snapshot["classification"] == "Greed"
    assert snapshot["previous_value"] == 69.0
    assert snapshot["change"] == -7.0
    assert snapshot["timestamp"].endswith("+00:00")


def test_sentiment_factor_maps_index_to_score(monkeypatch):
    class FakeAdapter:
        def snapshot(self):
            return {
                "value": 27.0,
                "classification": "Fear",
                "previous_value": 31.0,
                "change": -4.0,
                "timestamp": "2026-09-02T00:00:00+00:00",
            }

    result = sentiment_factor(FakeAdapter())(None)
    assert result.name == "sentiment"
    assert result.status == "OK"
    assert result.score == 27.0
    assert result.confidence == 0.85
    assert result.provider == "ALTERNATIVE_ME"
    assert result.details["classification"] == "Fear"
    assert result.details["change_1d"] == -4.0


def test_sentiment_factor_fails_closed(monkeypatch):
    class BrokenAdapter:
        def snapshot(self):
            raise ValueError("bad payload")

    result = sentiment_factor(BrokenAdapter())(None)
    assert result.name == "sentiment"
    assert result.status == "UNAVAILABLE"
    assert result.score is None
    assert result.provider == "ALTERNATIVE_ME"
