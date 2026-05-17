from __future__ import annotations

from research_agent.sources.prices.price_provider_base import PriceProviderBase


class YFinancePriceProvider(PriceProviderBase):
    def get_history(self, ticker: str, start: str, end: str):
        raise NotImplementedError("YFinancePriceProvider is optional and not enabled in the deterministic core build.")
