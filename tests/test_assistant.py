from iea.assistant import build_response, detect_intent


def test_detect_intents_in_persian():
    assert detect_intent("الان وضعیت نقدینگی و بانک مرکزی چیه؟") == "monetary"
    assert detect_intent("وضعیت بازار بورس ایران") == "market"
    assert detect_intent("ریسک فعلی چقدر است؟") == "risk"
    assert detect_intent("برای سرمایه من چه کار کنم؟") == "portfolio"


def test_market_response_preserves_no_trade_guard():
    report = {
        "status": "warning",
        "finished_at": "2026-09-06T06:00:00+00:00",
        "health_status": "WARNING",
        "intelligence": {
            "market_status": "CLOSED",
            "regime": "NEUTRAL",
            "score": 50,
            "coverage": 0.75,
            "decision": {"action": "NO_TRADE", "reason": "stale"},
            "data_quality": {"status": "DEGRADED", "stale_factors": ["trend"]},
        },
        "central_bank": {"ingestion_status": "NOT_CONFIGURED"},
    }
    result = build_response("وضعیت بازار چیه؟", report)
    assert result["answer"]["action"] == "NO_TRADE"
    assert result["answer"]["data_quality"]["stale_factors"] == ["trend"]


def test_monetary_response_exposes_core_indicators():
    report = {
        "status": "ok",
        "finished_at": "2026-09-06T06:00:00+00:00",
        "central_bank": {
            "ingestion_status": "CONNECTED",
            "indicator_count": 3,
            "missing_indicators": [],
            "indicators": {
                "liquidity_m2": {"value": 100, "unit": "IRR bn"},
                "monetary_base": {"value": 40, "unit": "IRR bn"},
                "bank_credit": {"value": 70, "unit": "IRR bn"},
            },
        },
    }
    result = build_response("نقدینگی و پایه پولی چطور است؟", report)
    assert result["intent"] == "monetary"
    assert result["answer"]["indicators"]["liquidity_m2"]["value"] == 100
    assert result["answer"]["indicators"]["monetary_base"]["value"] == 40
