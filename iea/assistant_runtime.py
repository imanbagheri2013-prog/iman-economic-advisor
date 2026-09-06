from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from .assistant import build_response
from .report_service import load_latest_report

DEFAULT_REPORT_PATH = Path("health_report.json")


def load_report(path=DEFAULT_REPORT_PATH):
    return load_latest_report(path)


def answer(question, report_path=DEFAULT_REPORT_PATH):
    report = load_report(report_path)
    return build_response(question, report)


def main():
    parser = argparse.ArgumentParser(description="IEA deterministic assistant runtime")
    parser.add_argument("question")
    parser.add_argument("--report", default=str(DEFAULT_REPORT_PATH))
    args = parser.parse_args()
    print(json.dumps(answer(args.question, args.report), ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
