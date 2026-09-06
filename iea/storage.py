import json
import sqlite3
from pathlib import Path

from .models import Observation


SCHEMA = """
CREATE TABLE IF NOT EXISTS observations(
    provider TEXT,
    series_id TEXT,
    date TEXT,
    value REAL,
    retrieved_at TEXT,
    realtime_start TEXT,
    realtime_end TEXT,
    quality REAL,
    status TEXT,
    UNIQUE(provider, series_id, date, realtime_start, realtime_end)
);

CREATE INDEX IF NOT EXISTS idx_series_date
ON observations(provider, series_id, date);

CREATE TABLE IF NOT EXISTS central_bank_observations(
    indicator TEXT,
    value REAL,
    unit TEXT,
    observed_at TEXT,
    retrieved_at TEXT,
    source TEXT,
    frequency TEXT,
    source_url TEXT,
    revision INTEGER NOT NULL DEFAULT 0,
    metadata TEXT,
    UNIQUE(indicator, observed_at, source)
);

CREATE INDEX IF NOT EXISTS idx_cbi_indicator_date
ON central_bank_observations(indicator, observed_at);

CREATE TABLE IF NOT EXISTS portfolio_snapshots(
    snapshot_id INTEGER PRIMARY KEY AUTOINCREMENT,
    observed_at TEXT NOT NULL,
    capital REAL NOT NULL,
    cash REAL NOT NULL,
    equity REAL NOT NULL,
    current_exposure REAL NOT NULL,
    current_risk REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    unrealized_pnl REAL NOT NULL,
    drawdown REAL NOT NULL,
    state_json TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_portfolio_snapshot_time
ON portfolio_snapshots(observed_at);
"""


class Store:
    def __init__(self, path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.con = sqlite3.connect(self.path)
        self.con.executescript(SCHEMA)
        self.con.commit()

    def upsert(self, obs: Observation):
        self.con.execute(
            """
            INSERT OR REPLACE INTO observations
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                obs.provider, obs.series_id, obs.date.isoformat(), obs.value,
                obs.retrieved_at.isoformat(), obs.realtime_start.isoformat() if obs.realtime_start else None,
                obs.realtime_end.isoformat() if obs.realtime_end else None, obs.quality, obs.status,
            ),
        )
        self.con.commit()

    def upsert_central_bank(self, observation):
        self.con.execute(
            """
            INSERT OR REPLACE INTO central_bank_observations
            (indicator, value, unit, observed_at, retrieved_at, source,
             frequency, source_url, revision, metadata)
            VALUES (?, ?, ?, ?, datetime('now'), ?, ?, ?, ?, ?)
            """,
            (
                observation.indicator, observation.value, observation.unit, observation.observed_at,
                observation.source, observation.frequency, observation.source_url,
                int(observation.revision), json.dumps(observation.metadata or {}, ensure_ascii=False),
            ),
        )
        self.con.commit()

    def central_bank_observations(self):
        from .central_bank import MonetaryObservation
        rows = self.con.execute(
            """SELECT indicator, value, unit, observed_at, source, frequency,
                      source_url, revision, metadata
               FROM central_bank_observations ORDER BY observed_at ASC"""
        ).fetchall()
        return [
            MonetaryObservation(
                indicator=row[0], value=row[1], unit=row[2], observed_at=row[3], source=row[4],
                frequency=row[5], source_url=row[6], revision=bool(row[7]), metadata=json.loads(row[8] or "{}"),
            ) for row in rows
        ]

    def save_portfolio_snapshot(self, state: dict):
        """Persist a normalized portfolio snapshot without embedding a fixed capital amount."""
        self.con.execute(
            """INSERT INTO portfolio_snapshots
               (observed_at, capital, cash, equity, current_exposure, current_risk,
                realized_pnl, unrealized_pnl, drawdown, state_json)
               VALUES (datetime('now'), ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                float(state["capital"]), float(state["cash"]), float(state["equity"]),
                float(state["current_exposure"]), float(state["current_risk"]),
                float(state.get("realized_pnl", 0.0)), float(state.get("unrealized_pnl", 0.0)),
                float(state.get("drawdown", 0.0)), json.dumps(state, ensure_ascii=False),
            ),
        )
        self.con.commit()

    def latest_portfolio_snapshot(self):
        row = self.con.execute(
            "SELECT state_json FROM portfolio_snapshots ORDER BY snapshot_id DESC LIMIT 1"
        ).fetchone()
        return json.loads(row[0]) if row else None

    def count(self):
        return self.con.execute("SELECT COUNT(*) FROM observations").fetchone()[0]

    def count_central_bank(self):
        return self.con.execute("SELECT COUNT(*) FROM central_bank_observations").fetchone()[0]

    def count_portfolio_snapshots(self):
        return self.con.execute("SELECT COUNT(*) FROM portfolio_snapshots").fetchone()[0]

    def close(self):
        self.con.close()
