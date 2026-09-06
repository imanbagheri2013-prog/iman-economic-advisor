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
            "monetary_growth": {
                "monetary_base_growth": 12.5,
                "liquidity_growth": 18.0,
                "bank_credit_growth": 9.0,
            },
            "monetary_impulse": {"direction": "EXPANSION", "score": 15.25},
            "monetary_policy_index": {"direction": "EXPANSIONARY", "score": 22.0},
            "policy_transmission": {"currency_in_circulation_growth": 10.0},
            "revision_count": 2,
            "stored_observation_count": 25,
        },
    }
    result = build_response("نقدینگی و پایه پولی چطور است؟", report)
    assert result["intent"] == "monetary"
    assert result["answer"]["indicators"]["liquidity_m2"]["value"] == 100
    assert result["answer"]["indicators"]["monetary_base"]["value"] == 40
    assert result["answer"]["monetary_growth"]["liquidity_growth"] == 18.0
    assert result["answer"]["monetary_impulse"]["direction"] == "EXPANSION"
    assert result["answer"]["monetary_policy_index"]["score"] == 22.0
    assert result["answer"]["policy_transmission"]["currency_in_circulation_growth"] == 10.0
    assert result["answer"]["revision_count"] == 2
    assert result["answer"]["stored_observation_count"] == 25


def test_portfolio_response_includes_monetary_context():
    report = {
        "status": "ok",
        "finished_at": "2026-09-06T06:00:00+00:00",
        "health_status": "HEALTHY",
        "advisor": {"action": "HOLD"},
        "intelligence": {"decision": {"action": "HOLD"}},
        "central_bank": {
            "ingestion_status": "CONNECTED",
            "indicator_count": 1,
            "indicators": {"liquidity_m2": {"value": 100}},
            "monetary_policy_index": {"direction": "NEUTRAL_OR_MIXED"},
        },
    }
    result = build_response("برای سبد سرمایه چه کار کنم؟", report)
    assert result["answer"]["monetary"]["monetary_policy_index"]["direction"] == "NEUTRAL_OR_MIXED"
