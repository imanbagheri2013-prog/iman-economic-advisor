from __future__ import annotations

from typing import Any


def _number(*values: Any) -> float | None:
    for value in values:
        if value is None or value == "":
            continue
        try:
            return float(value)
        except (TypeError, ValueError):
            continue
    return None


def _relative(value: float | None, peer: float | None) -> dict[str, Any]:
    if value is None or peer is None or peer <= 0:
        return {"ratio": None, "discount_pct": None, "status": "unavailable"}
    ratio = value / peer
    return {
        "ratio": round(ratio, 4),
        "discount_pct": round((1.0 - ratio) * 100.0, 2),
        "status": "discount" if ratio < 1 else ("premium" if ratio > 1 else "inline"),
    }


def valuation_diagnostics(instrument: dict[str, Any]) -> dict[str, Any]:
    """Build fail-closed valuation diagnostics from provider-native fields.

    No peer or historical value is invented. Historical percentile is emitted
    only when the provider supplies it.
    """
    pe = _number(instrument.get("pe"), instrument.get("pE"))
    forward_pe = _number(instrument.get("forwardPE"), instrument.get("forwardPe"), instrument.get("forward_pe"))
    pb = _number(instrument.get("pb"), instrument.get("pB"))
    ps = _number(instrument.get("ps"), instrument.get("pS"))
    ev_ebitda = _number(instrument.get("evEbitda"), instrument.get("evEBITDA"), instrument.get("ev_ebitda"))
    ev_sales = _number(instrument.get("evSales"), instrument.get("ev_sales"))
    sector_pe = _number(instrument.get("sectorPE"), instrument.get("sectorPe"), instrument.get("sector_pe"))
    sector_pb = _number(instrument.get("sectorPB"), instrument.get("sectorPb"), instrument.get("sector_pb"))
    sector_ps = _number(instrument.get("sectorPS"), instrument.get("sectorPs"), instrument.get("sector_ps"))
    sector_ev_ebitda = _number(instrument.get("sectorEbitda"), instrument.get("sectorEVEBITDA"), instrument.get("sector_ev_ebitda"))
    sector_ev_sales = _number(instrument.get("sectorEVSales"), instrument.get("sector_ev_sales"))
    dividend_yield = _number(instrument.get("dividendYield"), instrument.get("dividend_yield_pct"))
    historical_pe_percentile = _number(instrument.get("historicalPEPercentile"), instrument.get("historical_pe_percentile"))

    relative = {
        "pe": _relative(pe, sector_pe),
        "pb": _relative(pb, sector_pb),
        "ps": _relative(ps, sector_ps),
        "ev_ebitda": _relative(ev_ebitda, sector_ev_ebitda),
        "ev_sales": _relative(ev_sales, sector_ev_sales),
    }
    flags: list[str] = []
    if pe is not None and pe <= 0:
        flags.append("non_positive_pe")
    for name, item in relative.items():
        if item["status"] == "unavailable":
            flags.append(f"{name}_sector_comparison_unavailable")
        elif item["ratio"] <= 0.8:
            flags.append(f"{name}_discount_to_sector")
        elif item["ratio"] >= 1.2:
            flags.append(f"{name}_premium_to_sector")

    historical_status = "unavailable"
    if historical_pe_percentile is not None:
        historical_status = "lower_than_history" if historical_pe_percentile < 30 else (
            "higher_than_history" if historical_pe_percentile > 70 else "mid_range"
        )

    return {
        "pe": pe,
        "forward_pe": forward_pe,
        "pb": pb,
        "ps": ps,
        "ev_ebitda": ev_ebitda,
        "ev_sales": ev_sales,
        "dividend_yield_pct": dividend_yield,
        "sector_pe": sector_pe,
        "sector_pb": sector_pb,
        "sector_ps": sector_ps,
        "sector_ev_ebitda": sector_ev_ebitda,
        "sector_ev_sales": sector_ev_sales,
        "historical_pe_percentile": historical_pe_percentile,
        "historical_pe_status": historical_status,
        "pe_vs_sector": relative["pe"]["ratio"],
        "pe_discount_pct": relative["pe"]["discount_pct"],
        "relative": relative,
        "flags": flags,
    }
