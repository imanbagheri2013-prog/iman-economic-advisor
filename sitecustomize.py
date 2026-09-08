from __future__ import annotations

import os


if os.getenv("IEA_USE_IRAN_MARKET_MIRROR") == "1":
    try:
        import iea.providers.iran_market as iran_market_module
        from iea.providers.iran_market_mirror import FallbackIranMarketProvider

        iran_market_module.IranMarketProvider = FallbackIranMarketProvider
    except Exception:
        # Never prevent the application from starting because the optional
        # mirror patch is unavailable; the original provider remains usable.
        pass
