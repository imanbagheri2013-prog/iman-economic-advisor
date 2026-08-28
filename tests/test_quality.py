from datetime import datetime, timezone
from iea.quality import quality

def test_valid():
    assert quality(1, datetime.now(timezone.utc)) == 100.0

def test_missing():
    assert quality(None, datetime.now(timezone.utc)) == 0.0
