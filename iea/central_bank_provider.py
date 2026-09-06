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


def _configured_sources() -> list[str]:
    """Return sources in trust order: official/configured first, fallbacks next."""
    sources: list[str] = []
    primary = os.getenv("IEA_CBI_DATA_URL", "").strip()
    if primary:
        sources.append(primary)
    for value in os.getenv("IEA_CBI_FALLBACK_URLS", "").split(","):
        target = value.strip()
        if target and target not in sources:
            sources.append(target)
    return sources


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
    """Parse JSON or CSV using the stable CBI ingestion contract."""
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


def _validate_observations(observations: list[MonetaryObservation]) -> list[MonetaryObservation]:
    now = datetime.now(timezone.utc)
    for observation in observations:
        parsed = datetime.fromisoformat(observation.observed_at.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        if parsed > now:
            raise ValueError(f"CBI observation is in the future: {observation.observed_at}")
    return observations


def fetch_observations(
    url: str | None = None,
    *,
    timeout: int = DEFAULT_TIMEOUT,
) -> list[MonetaryObservation]:
    """Fetch CBI data with deterministic primary/fallback source ordering.

    The primary source should be an official CBI export/feed. Fallback URLs
    are explicit configuration rather than undocumented endpoints. A source
    is accepted only when it responds successfully and contains valid rows.
    """
    explicit_source = url is not None
    sources = [url] if explicit_source else _configured_sources()
    sources = [source for source in sources if source]
    if not sources:
        return []

    errors: list[str] = []
    for target in sources:
        try:
            response = requests.get(target, timeout=timeout)
            response.raise_for_status()
            observations = parse_payload(response.text, response.headers.get("content-type", ""))
            return _validate_observations(observations)
        except ValueError:
            if explicit_source:
                raise
            errors.append(f"{target}: invalid CBI payload or observation")
        except Exception as exc:
            errors.append(f"{target}: {exc}")

    raise RuntimeError("All configured CBI data sources failed: " + " | ".join(errors))
