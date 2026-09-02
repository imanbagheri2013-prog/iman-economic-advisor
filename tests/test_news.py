from iea.news import GDELTNewsAdapter, news_risk_factor


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def test_gdelt_adapter_parses_articles(monkeypatch):
    payload = {
        "articles": [
            {"title": "Bitcoin rises after ETF approval", "url": "https://example.com/1", "domain": "example.com", "seendate": "20260902160000"},
            {"title": "Crypto exchange hit by hack", "url": "https://example.com/2", "domain": "example.com", "seendate": "20260902150000"},
        ]
    }

    def fake_get(url, params, timeout):
        assert url == "https://api.gdeltproject.org/api/v2/doc/doc"
        assert params["query"] == '(bitcoin OR crypto OR cryptocurrency OR ethereum)'
        assert params["mode"] == "artlist"
        assert params["format"] == "json"
        assert params["timespan"] == "6h"
        assert params["maxrecords"] == 25
        assert params["sort"] == "datedesc"
        assert timeout == 10.0
        return FakeResponse(payload)

    monkeypatch.setattr("iea.news.requests.get", fake_get)
    snapshot = GDELTNewsAdapter().snapshot()

    assert snapshot["count"] == 2
    assert snapshot["articles"][1]["title"] == "Crypto exchange hit by hack"
    assert snapshot["source"] == "GDELT"


def test_news_risk_factor_scores_headline_risk():
    class FakeAdapter:
        def snapshot(self):
            return {
                "articles": [
                    {"title": "Bitcoin rises after ETF approval"},
                    {"title": "Major crypto exchange hit by hack and fraud investigation"},
                ],
                "timestamp": "2026-09-02T16:00:00+00:00",
            }

    result = news_risk_factor(FakeAdapter())(None)
    assert result.name == "news_risk"
    assert result.status == "OK"
    assert result.provider == "GDELT"
    assert result.score < 100.0
    assert result.details["article_count"] == 2
    assert result.details["risk_score"] > 0
    assert result.details["risk_regime"] == "LOW_RISK"
    assert result.details["top_risk_headlines"][0]["title"].startswith("Major crypto exchange")


def test_news_risk_factor_fails_closed():
    class BrokenAdapter:
        def snapshot(self):
            raise ValueError("bad payload")

    result = news_risk_factor(BrokenAdapter())(None)
    assert result.name == "news_risk"
    assert result.status == "UNAVAILABLE"
    assert result.score is None
    assert result.provider == "GDELT"
