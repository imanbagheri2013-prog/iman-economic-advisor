from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Callable, Mapping


@dataclass(frozen=True)
class TsetmcInstrument:
    ins_code: str
    symbol: str
    name: str | None = None
    market: str | None = None
    sector: str | None = None


@dataclass(frozen=True)
class TsetmcPriceSnapshot:
    ins_code: str
    date: str
    close: float
    last: float | None = None
    volume: float = 0.0
    value: float | None = None
    trade_count: int | None = None
    buy_real_volume: float | None = None
    sell_real_volume: float | None = None
    buy_legal_volume: float | None = None
    sell_legal_volume: float | None = None


def _number(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _required_number(value: Any, name: str) -> float:
    number = _number(value)
    if number is None:
        raise ValueError(f"{name} must be numeric")
    return number


def parse_instrument(payload: Mapping[str, Any]) -> TsetmcInstrument:
    code = payload.get("insCode") or payload.get("ins_code")
    symbol = payload.get("lVal18") or payload.get("symbol") or payload.get("symbolName")
    if not code or not symbol:
        raise ValueError("instrument payload requires insCode and symbol")
    return TsetmcInstrument(
        ins_code=str(code),
        symbol=str(symbol),
        name=payload.get("lVal30") or payload.get("name"),
        market=payload.get("market") or payload.get("cgrValCot"),
        sector=payload.get("sector") or payload.get("sectorName"),
    )


def parse_price(payload: Mapping[str, Any]) -> TsetmcPriceSnapshot:
    code = payload.get("insCode") or payload.get("ins_code")
    date = payload.get("dEven") or payload.get("date")
    close = payload.get("pClosing") if "pClosing" in payload else payload.get("close")
    if not code or not date:
        raise ValueError("price payload requires insCode and date")
    return TsetmcPriceSnapshot(
        ins_code=str(code),
        date=str(date),
        close=_required_number(close, "close"),
        last=_number(payload.get("pDrCotVal") if "pDrCotVal" in payload else payload.get("last")),
        volume=_number(payload.get("qTotTran5J") if "qTotTran5J" in payload else payload.get("volume")) or 0.0,
        value=_number(payload.get("qTotCap") if "qTotCap" in payload else payload.get("value")),
        trade_count=int(payload["zTotTran"] if "zTotTran" in payload and payload["zTotTran"] is not None else payload.get("trade_count")) if (payload.get("zTotTran") is not None or payload.get("trade_count") is not None) else None,
        buy_real_volume=_number(payload.get("buyRealVolume") or payload.get("buy_real_volume")),
        sell_real_volume=_number(payload.get("sellRealVolume") or payload.get("sell_real_volume")),
        buy_legal_volume=_number(payload.get("buyLegalVolume") or payload.get("buy_legal_volume")),
        sell_legal_volume=_number(payload.get("sellLegalVolume") or payload.get("sell_legal_volume")),
    )


class TsetmcClient:
    """Small dependency-free adapter; transport is injected for testability."""

    def __init__(self, transport: Callable[[str], Any], base_url: str = "https://cdn.tsetmc.com/api"):
        self.transport = transport
        self.base_url = base_url.rstrip("/")

    def instrument_search(self, query: str) -> Any:
        return self.transport(f"{self.base_url}/Instrument/GetInstrumentSearch/{query}")

    def instrument_info(self, ins_code: str) -> Any:
        return self.transport(f"{self.base_url}/Instrument/GetInstrumentInfo/{ins_code}")

    def closing_prices(self, ins_code: str, days: int = 365) -> Any:
        if days <= 0:
            raise ValueError("days must be positive")
        return self.transport(f"{self.base_url}/ClosingPrice/GetClosingPriceDailyList/{ins_code}/{days}")

    def client_type_history(self, ins_code: str) -> Any:
        return self.transport(f"{self.base_url}/ClientType/GetClientTypeHistory/{ins_code}")

    def shareholders(self, ins_code: str) -> Any:
        return self.transport(f"{self.base_url}/Shareholder/GetInstrumentShareHolderLast/{ins_code}")

    def codal_publishers(self, symbol: str) -> Any:
        return self.transport(f"{self.base_url}/Codal/GetCodalPublisherBySymbol/{symbol}")
