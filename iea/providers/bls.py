import os, requests
from datetime import datetime, timezone
from ..models import Observation
from ..quality import quality

URL = 'https://api.bls.gov/publicAPI/v2/timeseries/data/'

class BLS:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv('BLS_API_KEY')

    def observations(self, series_id, start_year, end_year):
        payload = {'seriesid':[series_id], 'startyear':str(start_year),
                   'endyear':str(end_year)}
        if self.api_key:
            payload['registrationkey'] = self.api_key
        r = requests.post(URL, json=payload, timeout=30)
        r.raise_for_status()
        now = datetime.now(timezone.utc)
        out = []
        for series in r.json().get('Results', {}).get('series', []):
            for item in series.get('data', []):
                try:
                    value = float(str(item.get('value')).replace(',', ''))
                except (ValueError, TypeError):
                    value = None
                period = item.get('period', 'M01')
                month = int(period[1:]) if period.startswith('M') else 1
                date = datetime(int(item['year']), min(max(month,1),12), 1, tzinfo=timezone.utc)
                out.append(Observation(provider='bls', series_id=series_id, date=date,
                    value=value, retrieved_at=now,
                    quality=quality(value, now, 40),
                    status='OK' if value is not None else 'MISSING'))
        return out
