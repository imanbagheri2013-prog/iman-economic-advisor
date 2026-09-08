from __future__ import annotations

import pathlib
import sys

# Railway starts this script from /app/scripts; add the project root so the
# packaged `iea` module is importable regardless of the working directory.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from iea.providers.iran_market_mirror import FallbackIranMarketProvider

SYMBOLS = ["فولاد", "فملی", "شستا", "خودرو", "وبملت"]


def main() -> int:
    provider = FallbackIranMarketProvider()
    passed = 0
    for symbol in SYMBOLS:
        try:
            snap = provider.snapshot(symbol)
            print(
                f"TSETMC FALLBACK OK symbol={symbol} source={snap.source} "
                f"price={snap.price} previous={snap.previous_close} volume={snap.volume}",
                flush=True,
            )
            passed += 1
        except Exception as exc:
            print(f"TSETMC FALLBACK FAIL symbol={symbol} error={type(exc).__name__}: {exc}", flush=True)
    print(f"TSETMC FALLBACK SUMMARY passed={passed} total={len(SYMBOLS)}", flush=True)
    return 0 if passed == len(SYMBOLS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
