from datetime import datetime, timezone
from iea.models import Observation
from iea.storage import Store

def test_store(tmp_path):
    s = Store(str(tmp_path/'test.sqlite3'))
    s.upsert(Observation(provider='test',series_id='X',
        date=datetime(2026,1,1,tzinfo=timezone.utc),value=1.2,
        retrieved_at=datetime.now(timezone.utc),quality=100))
    assert s.count() == 1
