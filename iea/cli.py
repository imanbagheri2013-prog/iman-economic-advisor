import os, sys
from dotenv import load_dotenv
load_dotenv()

def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else 'health'
    if cmd == 'health':
        print('IEA Data Engine v1.1 — READY')
        print('FRED:', 'configured' if os.getenv('FRED_API_KEY') else 'MISSING')
        print('BLS:', 'configured' if os.getenv('BLS_API_KEY') else 'optional/missing')
        print('DB:', os.getenv('IEA_DB_PATH','data/iea.sqlite3'))
    elif cmd == 'pull':
        from .pipeline import pull
        print('Stored observations:', pull().count())
    elif cmd == 'report':
        from .report import report
        print(report())
    else:
        raise SystemExit('Usage: python -m iea.cli [health|pull|report]')

if __name__ == '__main__':
    main()
import os
import sys

from dotenv import load_dotenv

load_dotenv()


def main():
    cmd = sys.argv[1] if len(sys.argv) > 1 else "health"

    if cmd == "health":
        print("IEA Data Engine v1.2 — READY")
        print(
            "FRED:",
            "configured" if os.getenv("FRED_API_KEY") else "MISSING",
        )
        print(
            "BLS:",
            "configured" if os.getenv("BLS_API_KEY") else "optional/missing",
        )
        print(
            "DB:",
            os.getenv("IEA_DB_PATH", "data/iea.sqlite3"),
        )

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

    else:
        raise SystemExit(
            "Usage: python -m iea.cli [health|pull|report]"
        )


if __name__ == "__main__":
    main()
