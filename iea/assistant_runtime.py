from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .assistant import build_response


DEFAULT_REPORT_PATH = Path("health_report.json")


def load_report(path: str | Path = DEFAULT_REPORT_PATH) -> dict[str, Any]:
    """Load the latest scheduler report without fabricating missing data."""
    report_path = Path(path)
    try:
        payload = json.loads(report_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise RuntimeError(f"Unable to load IEA report: {report_path}") from exc
    if not isinstance(payload, dict):
        raise ValueError("IEA report must contain a JSON object")
    return payload


def answer(question: str, report_path: str | Path = DEFAULT_REPORT_PATH) -> dict[str, Any]:
    """Build an assistant response from the latest trusted scheduler report."""
    report = load_report(report_path)
    return build_response(question, report)


def main() -> int:
    parser = argparse.ArgumentParser(description="IEA deterministic assistant runtime")
    parser.add_argument("question", help="Question to answer")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH), help="Path to the latest IEA health report")
    args = parser.parse_args()
    print(json.dumps(answer(args.question, args.report), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
