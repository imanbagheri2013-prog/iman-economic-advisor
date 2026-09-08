from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Iterable, Optional


@dataclass(frozen=True)
class MarketSnapshot:
    symbol: str
    observed_at: datetime
    price: float
    previous_close: Optional[float] = None
    volume: Optional[float] = None
    average_volume: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    source: str = "unknown"
    max_age_seconds: int = 300
    market_status: str = "OPEN"
    data_date: str | None = None

    @property
    def age_seconds(self) -> float:
        now = datetime.now(timezone.utc)
        observed = self.observed_at
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=timezone.utc)
        return max(0.0, (now - observed.astimezone(timezone.utc)).total_seconds())

    @property
    def fresh(self) -> bool:
        return self.age_seconds <= self.max_age_seconds

    @property
    def analyzable(self) -> bool:
        return self.fresh or self.market_status == "CLOSED"


@dataclass(frozen=True)
class MarketSignal:
    symbol: str
    action: str
    score: float
    confidence: float
    market_state: str
    reasons: tuple[str, ...]
    data_fresh: bool
    observed_at: str
    source: str
    analysis_action: str = "NO_TRADE"
    market_status: str = "OPEN"
    data_date: str | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "action": self.action,
            "score": self.score,
            "confidence": self.confidence,
            "market_state": self.market_state,
            "reasons": list(self.reasons),
            "data_fresh": self.data_fresh,
            "observed_at": self.observed_at,
            "source": self.source,
            "analysis_action": self.analysis_action,
            "market_status": self.market_status,
            "data_date": self.data_date,
        }


def _pct_change(price: float, previous: Optional[float]) -> Optional[float]:
    if previous is None or previous <= 0:
        return None
    return ((price - previous) / previous) * 100.0


def analyze_snapshot(snapshot: MarketSnapshot) -> MarketSignal:
    """Analyze live and closed snapshots without confusing the two."""
    observed = snapshot.observed_at
    if observed.tzinfo is None:
        observed = observed.replace(tzinfo=timezone.utc)

    if not snapshot.analyzable:
        return MarketSignal(
            symbol=snapshot.symbol, action="NO_TRADE", score=0.0, confidence=0.0,
            market_state="STALE", reasons=("market snapshot is stale",),
            data_fresh=False, observed_at=observed.isoformat(), source=snapshot.source,
            market_status=snapshot.market_status, data_date=snapshot.data_date,
        )

    change = _pct_change(snapshot.price, snapshot.previous_close)
    if change is None:
        return MarketSignal(
            symbol=snapshot.symbol, action="NO_TRADE", score=0.0, confidence=0.0,
            market_state="INSUFFICIENT_DATA", reasons=("previous close is missing or invalid",),
            data_fresh=snapshot.fresh, observed_at=observed.isoformat(), source=snapshot.source,
            market_status=snapshot.market_status, data_date=snapshot.data_date,
        )

    score = max(-100.0, min(100.0, change * 20.0))
    reasons: list[str] = [f"price_change={change:.2f}%"]
    if snapshot.volume is not None and snapshot.average_volume and snapshot.average_volume > 0:
        volume_ratio = snapshot.volume / snapshot.average_volume
        if volume_ratio >= 1.5:
            score += 15.0 if change > 0 else -15.0
            reasons.append(f"volume_ratio={volume_ratio:.2f}")
    if snapshot.high is not None and snapshot.low is not None and snapshot.high >= snapshot.low:
        range_size = snapshot.high - snapshot.low
        if range_size > 0:
            position = (snapshot.price - snapshot.low) / range_size
            if position >= 0.8:
                score += 5.0
                reasons.append("price near session high")
            elif position <= 0.2:
                score -= 5.0
                reasons.append("price near session low")

    score = max(-100.0, min(100.0, score))
    confidence = min(100.0, abs(score))
    if score >= 30:
        analysis_action, state = "BUY", "BULLISH"
    elif score <= -30:
        analysis_action, state = "SELL", "BEARISH"
    else:
        analysis_action, state = "WAIT", "NEUTRAL"

    executable_action = analysis_action if snapshot.fresh and snapshot.market_status != "CLOSED" else "NO_TRADE"
    if snapshot.market_status == "CLOSED":
        reasons.append("closed-market snapshot; analysis only, no live trade action")

    return MarketSignal(
        symbol=snapshot.symbol,
        action=executable_action,
        score=round(score, 2),
        confidence=round(confidence, 2),
        market_state=state if executable_action != "NO_TRADE" else f"{state}_CLOSED",
        reasons=tuple(reasons), data_fresh=snapshot.fresh,
        observed_at=observed.isoformat(), source=snapshot.source,
        analysis_action=analysis_action, market_status=snapshot.market_status,
        data_date=snapshot.data_date,
    )


def analyze_snapshots(snapshots: Iterable[MarketSnapshot]) -> dict[str, Any]:
    signals = [analyze_snapshot(snapshot) for snapshot in snapshots]
    actionable = [signal for signal in signals if signal.action in {"BUY", "SELL"}]
    return {
        "engine": "IEA Market Intelligence",
        "version": "1.1",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "count": len(signals),
        "actionable_count": len(actionable),
        "signals": [signal.as_dict() for signal in signals],
        "safety": {
            "stale_data_action": "NO_TRADE",
            "closed_market_action": "NO_TRADE",
            "missing_required_data_action": "NO_TRADE",
        },
    }
