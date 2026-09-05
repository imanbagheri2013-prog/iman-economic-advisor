from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable

from .models import Observation
from .storage import Store
from .tsetmc_adapter import TsetmcClient, TsetmcPriceSnapshot, parse_price


@dataclass(frozen=True)
class StockDataBatch:
    provider: str
    records: tuple[Observation, ...]
    instruments_processed: int
    records_written: int


def _timestamp() -> datetime:
    return datetime.now(timezone.utc)


def price_to_observations(snapshot: TsetmcPriceSnapshot) -> tuple[Observation, ...]:
    """Convert a normalized TSETMC price snapshot into Data Engine observations."""
    retrieved = _timestamp()
    values = {
        "close": snapshot.close,
        "last": snapshot.last,
        "volume": snapshot.volume,
        "value": snapshot.value,
        "trade_count": snapshot.trade_count,
        "buy_real_volume": snapshot.buy_real_volume,
        "sell_real_volume": snapshot.sell_real_volume,
        "buy_legal_volume": snapshot.buy_legal_volume,
        "sell_legal_volume": snapshot.sell_legal_volume,
    }
    observations: list[Observation] = []
    for metric, value in values.items():
        if value is None:
            continue
        observations.append(
            Observation(
                provider="TSETMC",
                series_id=f"{snapshot.ins_code}.{metric}",
                date=datetime.strptime(snapshot.date, "%Y%m%d"),
                value=float(value),
                retrieved_at=retrieved,
                quality=100.0,
                status="OK",
            )
        )
    return tuple(observations)


def build_price_batch(payloads: Iterable[dict[str, Any]]) -> StockDataBatch:
    """Normalize raw closing-price payloads into observations without I/O."""
    records: list[Observation] = []
    instruments: set[str] = set()
    for payload in payloads:
        snapshot = parse_price(payload)
        instruments.add(snapshot.ins_code)
        records.extend(price_to_observations(snapshot))
    return StockDataBatch(
        provider="TSETMC",
        records=tuple(records),
        instruments_processed=len(instruments),
        records_written=len(records),
    )


def ingest_price_payloads(store: Store, payloads: Iterable[dict[str, Any]]) -> StockDataBatch:
    """Persist normalized TSETMC price payloads in the shared Data Engine."""
    batch = build_price_batch(payloads)
    for observation in batch.records:
        store.upsert(observation)
    return batch


def collect_instrument_prices(
    client: TsetmcClient,
    store: Store,
    instruments: Iterable[str],
    days: int = 365,
) -> StockDataBatch:
    """Collect closing-price history for an instrument universe.

    Transport and source authentication remain outside this layer. The client
    is injected so scheduled production transport and deterministic tests use
    the same pipeline.
    """
    payloads: list[dict[str, Any]] = []
    for ins_code in instruments:
        response = client.closing_prices(ins_code, days=days)
        if isinstance(response, dict):
            rows = response.get("closingPriceDaily", response.get("data", []))
        else:
            rows = response
        if rows is None:
            continue
        payloads.extend(dict(row) for row in rows)
    return ingest_price_payloads(store, payloads)
