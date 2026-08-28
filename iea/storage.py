import sqlite3
from pathlib import Path
from .models import Observation

SCHEMA = '''
CREATE TABLE IF NOT EXISTS observations(
 provider TEXT, series_id TEXT, date TEXT, value REAL,
 retrieved_at TEXT, realtime_start TEXT, realtime_end TEXT,
 quality REAL, status TEXT,
 UNIQUE(provider, series_id, date, realtime_start, realtime_end)
);
CREATE INDEX IF NOT EXISTS idx_series_date ON observations(provider, series_id, date);
'''

class Store:
    def __init__(self, path):
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(path)
        self.con.executescript(SCHEMA)
        self.con.commit()

    def upsert(self, obs: Observation):
        self.con.execute(
            '''INSERT OR REPLACE INTO observations
            VALUES(?,?,?,?,?,?,?,?,?)''',
            (obs.provider, obs.series_id, obs.date.isoformat(), obs.value,
             obs.retrieved_at.isoformat(),
             obs.realtime_start.isoformat() if obs.realtime_start else None,
             obs.realtime_end.isoformat() if obs.realtime_end else None,
             obs.quality, obs.status))
        self.con.commit()

    def count(self):
        return self.con.execute("SELECT COUNT(*) FROM observations").fetchone()[0]
