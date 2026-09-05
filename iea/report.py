from __future__ import annotations

import os
import sqlite3
from typing import Any


def report() -> str:
    """Render the existing data-health report from the local observation DB."""
    db = os.getenv("IEA_DB_PATH", "data/iea.sqlite3")
    if not os.path.exists(db):
        return "No database yet. Run: python -m iea.cli pull"
    con = sqlite3.connect(db)
    try:
        rows = con.execute(
            """SELECT provider,series_id,date,value,quality,status
               FROM observations ORDER BY date DESC LIMIT 50"""
        ).fetchall()
    finally:
        con.close()

    lines = ["# IEA Data Health Report", ""]
    for row in rows:
        lines.append(
            f"- {row[0]}:{row[1]} | {row[2]} | value={row[3]} | "
            f"quality={row[4]} | {row[5]}"
        )
    return "\n".join(lines)


def advisor_report(advisor_result: dict[str, Any]) -> str:
    """Render the unified equity advisor result as a concise Markdown report."""
    if not isinstance(advisor_result, dict):
        raise ValueError("advisor result must be a JSON object")

    symbol = advisor_result.get("symbol", "UNKNOWN")
    analysis = advisor_result.get("analysis") or {}
    market = advisor_result.get("market") or {}
    decision = advisor_result.get("decision") or {}
    weights = advisor_result.get("weights") or {}

    lines = [
        f"# IEA Advisor Report — {symbol}",
        "",
        f"- Engine: `{advisor_result.get('engine', 'unknown')}`",
        f"- Combined score: **{advisor_result.get('combined_score', 'N/A')}**",
        f"- Equity score: **{analysis.get('final_score', 'N/A')}**",
        f"- Equity signal: **{analysis.get('final_signal', 'N/A')}**",
        f"- Market score: **{market.get('score', 'N/A')}**",
        f"- Market regime: **{market.get('regime', 'N/A')}**",
        f"- Market coverage: **{market.get('coverage', 'N/A')}**",
        f"- Weights: equity={weights.get('equity', 'N/A')}, market={weights.get('market', 'N/A')}",
        "",
        "## Decision",
        "",
        f"- Action: **{decision.get('action', 'N/A')}**",
        f"- Risk tier: `{decision.get('risk_tier', 'N/A')}`",
        f"- Conviction: **{decision.get('conviction', 'N/A')}**",
    ]

    reasons = analysis.get("reasons") or []
    if reasons:
        lines.extend(["", "## Analysis Reasons", ""])
        lines.extend(f"- {reason}" for reason in reasons)

    return "\n".join(lines)
