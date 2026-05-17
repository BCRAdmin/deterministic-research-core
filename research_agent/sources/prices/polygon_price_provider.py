from __future__ import annotations

from research_agent.sources.prices.price_provider_base import PriceProviderBase


class PolygonPriceProvider(PriceProviderBase):
    def get_history(self, ticker: str, start: str, end: str):
        raise NotImplementedError("PolygonPriceProvider requires an API key and is not enabled in the deterministic core build.")
