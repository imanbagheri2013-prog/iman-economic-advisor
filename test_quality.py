from datetime import datetime,timezone
from iea.quality import score
def test_score(): assert score(1,datetime.now(timezone.utc))==100
def test_missing(): assert score(None,datetime.now(timezone.utc))==0
