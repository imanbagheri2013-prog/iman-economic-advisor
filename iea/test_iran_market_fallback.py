from __future__ import annotations

from .providers.iran_market_mirror import FallbackIranMarketProvider

SYMBOLS = ["فولاد", "فملی", "شستا", "خودرو", "وبملت"]


def main() -> int:
    provider = FallbackIranMarketProvider()
    passed = 0
    for symbol in SYMBOLS:
        try:
            snap = provider.snapshot(symbol)
            print(f"TSETMC FALLBACK OK symbol={symbol} source={snap.source} price={snap.price} previous={snap.previous_close} volume={snap.volume}", flush=True)
            passed += 1
        except Exception as exc:
            print(f"TSETMC FALLBACK FAIL symbol={symbol} error={type(exc).__name__}: {exc}", flush=True)
    print(f"TSETMC FALLBACK SUMMARY passed={passed} total={len(SYMBOLS)}", flush=True)
    return 0 if passed == len(SYMBOLS) else 1


if __name__ == "__main__":
    raise SystemExit(main())
