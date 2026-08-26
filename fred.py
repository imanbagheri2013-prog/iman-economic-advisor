import os, requests
from datetime import datetime, timezone
from ..models import Observation
from ..quality import quality

URL = 'https://api.stlouisfed.org/fred/series/observations'

class FRED:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('FRED_API_KEY')
        if not self.api_key:
            raise RuntimeError('FRED_API_KEY is not set')

    def observations(self, series_id, limit=100):
        params = {'series_id':series_id, 'api_key':self.api_key,
                  'file_type':'json', 'sort_order':'desc', 'limit':limit}
        r = requests.get(URL, params=params, timeout=30)
        r.raise_for_status()
        now = datetime.now(timezone.utc)
        out = []
        for item in r.json().get('observations', []):
            raw = item.get('value')
            value = None if raw in (None, '.') else float(raw)
            date = datetime.fromisoformat(item['date']).replace(tzinfo=timezone.utc)
            out.append(Observation(provider='fred', series_id=series_id, date=date,
                value=value, retrieved_at=now, quality=quality(value, now),
                status='OK' if value is not None else 'MISSING'))
        return out
