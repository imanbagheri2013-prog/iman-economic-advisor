from datetime import datetime, timezone

def quality(value, retrieved_at, max_age_days=7):
    if value is None:
        return 0.0
    age = max(0.0, (datetime.now(timezone.utc) - retrieved_at).total_seconds()/86400)
    freshness = 60.0 * max(0.0, 1.0 - min(age/max_age_days, 1.0))
    return round(min(100.0, 40.0 + freshness), 2)
