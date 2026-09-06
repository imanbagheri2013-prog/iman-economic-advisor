from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


INTENTS = {
    "market": ("بازار", "بورس", "شاخص", "سهام", "market", "iran"),
    "monetary": ("بانک مرکزی", "نقدینگی", "پایه پولی", "چاپ پول", "m2", "m1", "monetary"),
    "risk": ("ریسک", "risk", "خطر"),
    "portfolio": ("سبد", "سرمایه", "پرتفوی", "portfolio", "capital"),
}


def detect_intent(question: str) -> str:
    text = (question or "").strip().lower()
    for intent, keywords in INTENTS.items():
        if any(keyword.lower() in text for keyword in keywords):
            return intent
    return "overview"


def _market_summary(report: dict[str, Any]) -> dict[str, Any]:
    intelligence = report.get("intelligence") or {}
    decision = intelligence.get("decision") or {}
    quality = intelligence.get("data_quality") or {}
    return {
        "market_status": intelligence.get("market_status"),
        "regime": intelligence.get("regime"),
        "score": intelligence.get("score"),
        "coverage": intelligence.get("coverage"),
        "action": decision.get("action", "NO_TRADE"),
        "reason": decision.get("reason"),
        "data_quality": quality,
    }


def _monetary_summary(report: dict[str, Any]) -> dict[str, Any]:
    monetary = report.get("central_bank") or {}
    indicators = monetary.get("indicators") or {}
    selected = {
        name: indicators[name]
        for name in (
            "monetary_base",
            "liquidity_m2",
            "m1",
            "quasi_money",
            "currency_in_circulation",
            "bank_deposits",
            "bank_credit",
            "bank_reserves",
            "reserve_requirement",
            "policy_rate",
            "interbank_rate",
            "government_deposits",
            "net_foreign_assets",
            "foreign_exchange_reserves",
        )
        if name in indicators
    }
    return {
        "ingestion_status": monetary.get("ingestion_status", "UNKNOWN"),
        "observed_indicator_count": monetary.get("indicator_count", 0),
        "missing_indicators": monetary.get("missing_indicators", []),
        "indicators": selected,
    }


def build_response(question: str, report: dict[str, Any]) -> dict[str, Any]:
    """Turn a scheduler report into a deterministic assistant response.

    The response is intentionally structured so a future chat/API layer can
    render it in Persian or another language without changing the data trust
    rules. It never turns missing or stale data into a BUY/SELL claim.
    """
    intent = detect_intent(question)
    response: dict[str, Any] = {
        "assistant": "IEA",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "intent": intent,
        "status": report.get("status", "unknown"),
        "data_timestamp": report.get("finished_at"),
    }

    if intent == "market":
        response["answer"] = _market_summary(report)
    elif intent == "monetary":
        response["answer"] = _monetary_summary(report)
    elif intent == "risk":
        response["answer"] = {
            "market": _market_summary(report),
            "monetary": _monetary_summary(report),
            "health_status": report.get("health_status"),
        }
    elif intent == "portfolio":
        response["answer"] = {
            "advisor": report.get("advisor"),
            "market": _market_summary(report),
            "health_status": report.get("health_status"),
        }
    else:
        response["answer"] = {
            "market": _market_summary(report),
            "monetary": _monetary_summary(report),
            "health_status": report.get("health_status"),
        }

    return response
