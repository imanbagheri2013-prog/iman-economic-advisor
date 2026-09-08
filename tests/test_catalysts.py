from iea.catalysts import detect_catalysts


def test_detects_positive_codal_catalyst():
    result = detect_catalysts([{"title": "انعقاد قرارداد جدید صادراتی", "date": "20260908"}])
    assert result["new_catalyst"] is True
    assert result["status"] == "positive"
    assert result["positive_count"] == 1


def test_detects_negative_codal_event():
    result = detect_catalysts([{"subject": "کاهش تولید و توقف خط", "date": "20260908"}])
    assert result["new_catalyst"] is False
    assert result["status"] == "negative"


def test_missing_or_mixed_events_fail_closed():
    assert detect_catalysts([])["new_catalyst"] is None
    result = detect_catalysts([{"title": "افزایش سرمایه"}, {"title": "کاهش تولید"}])
    assert result["new_catalyst"] is None
    assert result["status"] == "mixed"
