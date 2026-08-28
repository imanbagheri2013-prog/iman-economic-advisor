import sqlite3
from pathlib import Path
from .models import Observation

SCHEMA = '''
CREATE TABLE IF NOT EXISTS observations(
 provider TEXT NOT NULL, series_id TEXT NOT NULL, date TEXT NOT NULL,
 value REAL, retrieved_at TEXT NOT NULL, unit TEXT, frequency TEXT,
 quality REAL NOT NULL, status TEXT NOT NULL,
 UNIQUE(provider,series_id,date)
);
CREATE INDEX IF NOT EXISTS idx_obs ON observations(provider,series_id,date);
'''

class Store:
    def __init__(self,path):
        Path(path).parent.mkdir(parents=True,exist_ok=True)
        self.con=sqlite3.connect(path)
        self.con.executescript(SCHEMA)
        self.con.commit()
    def upsert(self,o:Observation):
        self.con.execute('''INSERT OR REPLACE INTO observations
        VALUES(?,?,?,?,?,?,?,?,?)''',
        (o.provider,o.series_id,o.date.isoformat(),o.value,
         o.retrieved_at.isoformat(),o.unit,o.frequency,o.quality,o.status))
        self.con.commit()
    def count(self):
        return self.con.execute('SELECT COUNT(*) FROM observations').fetchone()[0]
