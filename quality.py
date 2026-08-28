from datetime import datetime, timezone

def score(value, retrieved_at, max_age_days=7):
    if value is None:
        return 0.0
    age = max(0, (datetime.now(timezone.utc)-retrieved_at).total_seconds()/86400)
    freshness = 60 * max(0, 1-min(age/max_age_days,1))
    return round(40+freshness,2)
