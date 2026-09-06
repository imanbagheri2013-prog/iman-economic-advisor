from __future__ import annotations

import csv
import io
import json
import os
from datetime import datetime, timezone
from typing import Any

import requests

from .central_bank import MonetaryObservation, normalize_observation

DEFAULT_TIMEOUT = 20


def _configured_url() -> str | None:
    value = os.getenv("IEA_CBI_DATA_URL", "").strip()
    return value or None


def _parse_row(row: dict[str, Any]) -> MonetaryObservation:
    return normalize_observation(
        indicator=str(row["indicator"]),
        value=float(row["value"]),
        unit=str(row.get("unit") or "IRR"),
        observed_at=str(row["observed_at"]),
        frequency=row.get("frequency"),
        source=str(row.get("source") or "CBI"),
        source_url=row.get("source_url"),
        revision=str(row.get("revision", "false")).lower() in {"1", "true", "yes"},
        metadata=row.get("metadata") if isinstance(row.get("metadata"), dict) else {},
    )


def parse_payload(text: str, content_type: str = "") -> list[MonetaryObservation]:
    """Parse the stable ingestion contract used by the CBI adapter.

    Supported formats are JSON arrays/objects with an ``observations`` array
    and CSV with columns: indicator,value,unit,observed_at,frequency,source,
    source_url,revision. The upstream URL is intentionally configurable so
    official CBI exports can be used without hard-coding undocumented APIs.
    """
    stripped = text.lstrip()
    if "json" in content_type.lower() or stripped.startswith("[") or stripped.startswith("{"):
        payload = json.loads(text)
        rows = payload.get("observations", []) if isinstance(payload, dict) else payload
        if not isinstance(rows, list):
            raise ValueError("CBI JSON payload must contain an observations list")
        return [_parse_row(row) for row in rows]

    reader = csv.DictReader(io.StringIO(text))
    required = {"indicator", "value", "observed_at"}
    if not required.issubset(set(reader.fieldnames or [])):
        raise ValueError("CBI CSV must contain indicator,value,observed_at columns")
    return [_parse_row(row) for row in reader]


def fetch_observations(url: str | None = None, *, timeout: int = DEFAULT_TIMEOUT) -> list[MonetaryObservation]:
    target = url or _configured_url()
    if not target:
        return []
    response = requests.get(target, timeout=timeout)
    response.raise_for_status()
    observations = parse_payload(response.text, response.headers.get("content-type", ""))
    now = datetime.now(timezone.utc)
    for observation in observations:
        # Reject obviously malformed future observations while allowing
        # timezone-free historical source dates.
        parsed = datetime.fromisoformat(observation.observed_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed > now:
            raise ValueError(f"CBI observation is in the future: {observation.observed_at}")
    return observations
