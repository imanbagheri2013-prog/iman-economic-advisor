import csv
import io
import os
import time
from datetime import datetime, timezone

import requests

from ..models import Observation
from ..quality import quality

URL = "https://api.stlouisfed.org/fred/series/observations"
PUBLIC_CSV_URL = "https://fred.stlouisfed.org/graph/fredgraph.csv"
MAX_ATTEMPTS = 3
RETRY_DELAYS_SECONDS = (2, 5)


class FRED:
    def __init__(self, api_key=None):
        self.api_key = api_key or os.getenv("FRED_API_KEY")
        if not self.api_key:
            raise RuntimeError("FRED_API_KEY is not set")

    def observations(self, series_id, limit=100):
        return self._api_observations(series_id, limit)

    def _api_observations(self, series_id, limit):
        params = {
            "series_id": series_id,
            "api_key": self.api_key,
            "file_type": "json",
            "sort_order": "desc",
            "limit": limit,
        }
        response = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            response = requests.get(URL, params=params, timeout=30)
            if response.status_code not in {429, 500, 502, 503, 504} or attempt == MAX_ATTEMPTS:
                break
            retry_after = response.headers.get("Retry-After")
            try:
                delay = max(0, min(float(retry_after), 30)) if retry_after else RETRY_DELAYS_SECONDS[attempt - 1]
            except ValueError:
                delay = RETRY_DELAYS_SECONDS[attempt - 1]
            time.sleep(delay)
        response.raise_for_status()

        now = datetime.now(timezone.utc)
        out = []
        for item in response.json().get("observations", []):
            raw = item.get("value")
            value = None if raw in (None, ".") else float(raw)
            date = datetime.fromisoformat(item["date"]).replace(tzinfo=timezone.utc)
            out.append(
                Observation(
                    provider="fred",
                    series_id=series_id,
                    date=date,
                    value=value,
                    retrieved_at=now,
                    quality=quality(value, now),
                    status="OK" if value is not None else "MISSING",
                )
            )
        return out

    def _public_csv_observations(self, series_id, limit):
        response = requests.get(
            PUBLIC_CSV_URL,
            params={"id": series_id},
            timeout=30,
        )
        response.raise_for_status()
        rows = list(csv.DictReader(io.StringIO(response.text)))
        rows = rows[-limit:]
        now = datetime.now(timezone.utc)
        out = []
        for item in rows:
            raw = item.get(series_id)
            value = None if raw in (None, ".", "") else float(raw)
            date = datetime.fromisoformat(item["observation_date"]).replace(tzinfo=timezone.utc)
            out.append(
                Observation(
                    provider="fred",
                    series_id=series_id,
                    date=date,
                    value=value,
                    retrieved_at=now,
                    quality=quality(value, now),
                    status="OK" if value is not None else "MISSING",
                )
            )
        return out
