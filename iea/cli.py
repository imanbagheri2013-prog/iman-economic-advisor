import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def _run_advisor() -> dict:
    from .pipeline import pull
    from .runtime import build_live_equity_advisor_report, load_equity_payload

    payload_path = os.getenv("IEA_EQUITY_INPUT_PATH", "config/equity_input.json")
    payload = load_equity_payload(payload_path)
    store = pull()
    try:
        capital = payload.get("capital")
        return build_live_equity_advisor_report(
            store,
            payload,
            capital=float(capital) if capital is not None else None,
        )
    finally:
        store.close()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "health"

    if cmd == "health":
        print("IEA Data Engine v1.2 — READY")
        print("FRED:", "configured" if os.getenv("FRED_API_KEY") else "MISSING")
        print("BLS:", "configured" if os.getenv("BLS_API_KEY") else "optional/missing")
        print("DB:", os.getenv("IEA_DB_PATH", "data/iea.sqlite3"))

    elif cmd == "pull":
        from .pipeline import pull

        store = pull()
        try:
            print("Stored observations:", store.count())
        finally:
            store.close()

    elif cmd == "report":
        from .report import report

        print(report())

    elif cmd == "advisor":
        result = _run_advisor()
        print(json.dumps(result, ensure_ascii=False, indent=2, default=str))

    elif cmd == "advisor-report":
        from .report import advisor_report

        print(advisor_report(_run_advisor()))

    else:
        raise SystemExit(
            "Usage: python -m iea.cli [health|pull|report|advisor|advisor-report]"
        )


if __name__ == "__main__":
    main()
