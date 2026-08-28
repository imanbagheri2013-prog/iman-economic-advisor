import os, requests
from datetime import datetime, timezone
from ..models import Observation
from ..quality import score
URL='https://api.stlouisfed.org/fred/series/observations'
class FRED:
    def __init__(self,key=None):
        self.key=key or os.getenv('FRED_API_KEY')
        if not self.key: raise RuntimeError('FRED_API_KEY is not set')
    def observations(self,series_id,limit=50):
        r=requests.get(URL,params={'series_id':series_id,'api_key':self.key,
          'file_type':'json','sort_order':'desc','limit':limit},timeout=30)
        r.raise_for_status()
        now=datetime.now(timezone.utc); out=[]
        for x in r.json().get('observations',[]):
            v=None if x.get('value') in (None,'.') else float(x['value'])
            d=datetime.fromisoformat(x['date']).replace(tzinfo=timezone.utc)
            out.append(Observation(provider='fred',series_id=series_id,date=d,
              value=v,retrieved_at=now,quality=score(v,now),
              status='OK' if v is not None else 'MISSING'))
        return out
