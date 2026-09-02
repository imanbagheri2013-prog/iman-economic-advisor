from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

import requests


GDELT_DOC_API = "https://api.gdeltproject.org/api/v2/doc/doc"
NEWS_QUERY = '(bitcoin OR crypto OR cryptocurrency OR ethereum)'

# High-signal headlines that can create direct market or counterparty risk.
RISK_KEYWORDS = {
    "hack": 18,
    "exploit": 18,
    "breach": 15,
    "stolen": 15,
    "fraud": 15,
    "scam": 15,
    "bankrupt": 18,
    "bankruptcy": 18,
    "insolvency": 18,
    "lawsuit": 10,
    "ban": 14,
    "banned": 14,
    "sanction": 12,
    "sanctions": 12,
    "seized": 16,
    "seizure": 16,
    "shutdown": 12,
    "outage": 10,
    "crash": 12,
    "collapse": 15,
    "rejection": 10,
    "rejected": 10,
    "liquidation": 12,
    "investigation": 8,
    "charges": 10,
    "fine": 8,
    "war": 8,
}


class GDELTNewsAdapter:
    """Read recent crypto news headlines from the free GDELT DOC API."""

    def __init__(self, timeout: float = 10.0, timespan: str = "6h", maxrecords: int = 25) -> None:
        self.timeout = timeout
        self.timespan = timespan
        self.maxrecords = maxrecords

    def snapshot(self) -> dict[str, Any]:
        response = requests.get(
            GDELT_DOC_API,
            params={
                "query": NEWS_QUERY,
                "mode": "artlist",
                "format": "json",
                "timespan": self.timespan,
                "maxrecords": self.maxrecords,
                "sort": "datedesc",
            },
            timeout=self.timeout,
        )
        response.raise_for_status()
        payload = response.json()
        articles = payload.get("articles", []) if isinstance(payload, dict) else []
        if not isinstance(articles, list):
            raise ValueError("GDELT API returned an invalid articles payload")

        normalized: list[dict[str, Any]] = []
        for article in articles:
            if not isinstance(article, dict):
                continue
            title = str(article.get("title") or "").strip()
            if not title:
                continue
            normalized.append(
                {
                    "title": title,
                    "url": article.get("url"),
                    "domain": article.get("domain"),
                    "seendate": article.get("seendate"),
                }
            )

        return {
            "articles": normalized,
            "count": len(normalized),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source": "GDELT",
        }


def _headline_risk(title: str) -> int:
    text = title.lower()
    return min(100, sum(weight for keyword, weight in RISK_KEYWORDS.items() if keyword in text))


def news_risk_factor(adapter: GDELTNewsAdapter | None = None):
    """Return an eight-factor adapter where higher score means lower news risk."""
    source = adapter or GDELTNewsAdapter()

    def evaluate(_: Any):
        from .intelligence_v2 import FactorResult

        try:
            snapshot = source.snapshot()
        except (requests.RequestException, ValueError, KeyError, TypeError, OSError):
            return FactorResult("news_risk", "UNAVAILABLE", provider="GDELT")

        articles = snapshot.get("articles", [])
        risks = [_headline_risk(article["title"]) for article in articles if article.get("title")]
        risk_score = round(sum(risks) / len(risks), 2) if risks else 0.0
        market_score = round(100.0 - risk_score, 2)

        if risk_score >= 60:
            regime = "HIGH_RISK"
        elif risk_score >= 30:
            regime = "ELEVATED_RISK"
        else:
            regime = "LOW_RISK"

        top_risk = sorted(
            (
                {"title": article["title"], "risk": _headline_risk(article["title"])}
                for article in articles
                if article.get("title")
            ),
            key=lambda item: item["risk"],
            reverse=True,
        )[:5]

        return FactorResult(
            "news_risk",
            "OK",
            market_score,
            0.80 if articles else 0.50,
            "GDELT",
            snapshot.get("timestamp"),
            details={
                "query": NEWS_QUERY,
                "article_count": len(articles),
                "risk_score": risk_score,
                "risk_regime": regime,
                "top_risk_headlines": top_risk,
                "source": "GDELT",
            },
        )

    return evaluate
