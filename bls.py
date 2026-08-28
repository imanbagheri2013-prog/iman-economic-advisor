import os, requests
from datetime import datetime, timezone
from ..models import Observation
from ..quality import score
URL='https://api.bls.gov/publicAPI/v2/timeseries/data/'
class BLS:
    def __init__(self,key=None): self.key=key or os.getenv('BLS_API_KEY')
    def observations(self,series_id,start_year=2020,end_year=2026):
        p={'seriesid':[series_id],'startyear':str(start_year),'endyear':str(end_year)}
        if self.key: p['registrationkey']=self.key
        r=requests.post(URL,json=p,timeout=30); r.raise_for_status()
        now=datetime.now(timezone.utc); out=[]
        for s in r.json().get('Results',{}).get('series',[]):
            for x in s.get('data',[]):
                try: v=float(str(x.get('value')).replace(',',''))
                except (ValueError,TypeError): v=None
                period=x.get('period','M01')
                month=int(period[1:]) if period.startswith('M') else 1
                d=datetime(int(x['year']),min(max(month,1),12),1,tzinfo=timezone.utc)
                out.append(Observation(provider='bls',series_id=series_id,date=d,
                  value=v,retrieved_at=now,frequency='monthly',
                  quality=score(v,now,40),
                  status='OK' if v is not None else 'MISSING'))
        return out
