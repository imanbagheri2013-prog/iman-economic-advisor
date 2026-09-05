from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable


@dataclass(frozen=True)
class CapitalObservation:
    """Normalized observation describing where an institution is allocating capital."""

    institution: str
    institution_type: str
    country: str
    asset: str
    action: str
    value: float | None = None
    currency: str | None = None
    date: str | None = None
    source: str | None = None
    reason: str | None = None
    confidence: float = 0.5


@dataclass(frozen=True)
class CapitalSignal:
    """Aggregated advisory signal for a capital-allocation theme."""

    asset: str
    score: float
    direction: str
    observation_count: int
    confidence: float
    reasons: tuple[str, ...]


def _normalize_action(action: str) -> str:
    normalized = str(action).strip().upper().replace("-", "_").replace(" ", "_")
    aliases = {
        "BUY": "BUY", "PURCHASE": "BUY", "PURCHASES": "BUY",
        "ACCUMULATION": "BUY", "ACCUMULATE": "BUY",
        "SELL": "SELL", "SALES": "SELL", "REDUCTION": "SELL", "REDUCE": "SELL",
        "HOLD": "HOLD", "NEUTRAL": "HOLD",
    }
    return aliases.get(normalized, normalized)


def score_capital_observations(observations: Iterable[CapitalObservation]) -> tuple[CapitalSignal, ...]:
    """Aggregate normalized capital-allocation observations by asset."""
    buckets: dict[str, list[CapitalObservation]] = {}
    for observation in observations:
        if observation.confidence < 0 or observation.confidence > 1:
            raise ValueError("confidence must be between 0 and 1")
        asset = str(observation.asset).strip().upper()
        if not asset:
            raise ValueError("asset must not be empty")
        buckets.setdefault(asset, []).append(observation)

    signals: list[CapitalSignal] = []
    for asset, items in buckets.items():
        score = 0.0
        weighted_reasons: list[str] = []
        confidence_mass = 0.0
        for item in items:
            action = _normalize_action(item.action)
            weight = max(float(item.confidence), 0.0)
            if action == "BUY":
                score += weight
            elif action == "SELL":
                score -= weight
            elif action != "HOLD":
                continue
            confidence_mass += weight
            if item.reason:
                weighted_reasons.append(item.reason)
        direction = "ACCUMULATION" if score > 0 else "REDUCTION" if score < 0 else "NEUTRAL"
        confidence = min(1.0, confidence_mass / max(len(items), 1))
        signals.append(CapitalSignal(asset, round(score, 4), direction, len(items), round(confidence, 4), tuple(weighted_reasons)))
    return tuple(sorted(signals, key=lambda signal: abs(signal.score), reverse=True))


def central_bank_watchlist() -> tuple[str, ...]:
    return (
        "Federal Reserve", "European Central Bank", "People's Bank of China", "Bank of Japan",
        "Bank of England", "Swiss National Bank", "Reserve Bank of India", "Bank of Canada",
        "Reserve Bank of Australia", "Central Bank of Russia", "Central Bank of Türkiye",
        "Central Bank of the Republic of Iran",
    )


def iran_money_flow_and_sector_rotation(
    market_rows: Iterable[dict[str, Any]],
    client_rows: Iterable[dict[str, Any]],
) -> dict[str, Any]:
    """Build Iran-wide حقیقی/حقوقی flow and sector rotation from bulk TSETMC data.

    The function accepts normalized TSETMC rows and never invents missing values.
    ``market_rows`` should contain ``insCode``, sector name (``lSecVal`` when
    available), last price and traded value. ``client_rows`` should contain
    حقیقی/حقوقی buy/sell volumes or values. Value fields are preferred; when only
    volume is available, the market last price is used to convert volume to value.
    """
    clients: dict[str, dict[str, Any]] = {}
    for row in client_rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("insCode") or row.get("insCodeStr") or row.get("instrumentCode") or "").strip()
        if code:
            clients[code] = row

    def num(row: dict[str, Any], *keys: str) -> float | None:
        for key in keys:
            value = row.get(key)
            if value not in (None, ""):
                try:
                    return float(value)
                except (TypeError, ValueError):
                    pass
        return None

    def value(row: dict[str, Any], direct: tuple[str, ...], volume: tuple[str, ...], price: float | None) -> float | None:
        result = num(row, *direct)
        if result is not None:
            return result
        vol = num(row, *volume)
        if vol is not None and price is not None:
            return vol * price
        return None

    market_net = 0.0
    retail_net = 0.0
    legal_net = 0.0
    observed = 0
    sectors: dict[str, dict[str, float]] = {}

    for row in market_rows:
        if not isinstance(row, dict):
            continue
        code = str(row.get("insCode") or row.get("insCodeStr") or row.get("instrumentCode") or "").strip()
        client = clients.get(code)
        if client is None:
            continue
        price = num(row, "pl", "pDrCotVal", "price")
        sector = str(row.get("lSecVal") or row.get("sectorName") or row.get("sector") or "UNKNOWN").strip() or "UNKNOWN"

        retail_buy = value(client, ("buy_I_Value", "buyIValue", "buyIValueReal"), ("buy_I_Volume", "buyIVolume"), price)
        retail_sell = value(client, ("sell_I_Value", "sellIValue", "sellIValueReal"), ("sell_I_Volume", "sellIVolume"), price)
        legal_buy = value(client, ("buy_N_Value", "buyNValue", "buyNValueLegal"), ("buy_N_Volume", "buyNVolume"), price)
        legal_sell = value(client, ("sell_N_Value", "sellNValue", "sellNValueLegal"), ("sell_N_Volume", "sellNVolume"), price)
        if retail_buy is None or retail_sell is None or legal_buy is None or legal_sell is None:
            continue

        retail = retail_buy - retail_sell
        legal = legal_buy - legal_sell
        net = retail + legal
        market_net += net
        retail_net += retail
        legal_net += legal
        observed += 1

        bucket = sectors.setdefault(sector, {"net_flow": 0.0, "retail_net_flow": 0.0, "legal_net_flow": 0.0, "observations": 0.0})
        bucket["net_flow"] += net
        bucket["retail_net_flow"] += retail
        bucket["legal_net_flow"] += legal
        bucket["observations"] += 1.0

    sector_list = []
    for name, data in sectors.items():
        net = data["net_flow"]
        sector_list.append({
            "sector": name,
            "net_flow": round(net, 2),
            "retail_net_flow": round(data["retail_net_flow"], 2),
            "legal_net_flow": round(data["legal_net_flow"], 2),
            "observations": int(data["observations"]),
            "direction": "INFLOW" if net > 0 else "OUTFLOW" if net < 0 else "NEUTRAL",
        })
    sector_list.sort(key=lambda item: abs(item["net_flow"]), reverse=True)

    return {
        "provider": "TSETMC_CDN",
        "observed_symbols": observed,
        "retail_net_flow": round(retail_net, 2),
        "legal_net_flow": round(legal_net, 2),
        "total_net_flow": round(market_net, 2),
        "market_direction": "INFLOW" if market_net > 0 else "OUTFLOW" if market_net < 0 else "NEUTRAL",
        "top_inflow_sectors": [x for x in sector_list if x["net_flow"] > 0][:10],
        "top_outflow_sectors": [x for x in sector_list if x["net_flow"] < 0][:10],
        "sectors": sector_list,
    }
