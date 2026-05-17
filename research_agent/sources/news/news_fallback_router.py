from __future__ import annotations

from research_agent.sources.news.news_normalizer import normalize_news_items
from research_agent.sources.news.news_provider_base import NewsProviderBase


class NewsFallbackRouter:
    def __init__(self, providers: list[NewsProviderBase]):
        self.providers = providers

    def get_news(self, ticker: str, start: str, end: str) -> list[dict]:
        for provider in self.providers:
            items = provider.get_news(ticker, start, end)
            if items:
                return normalize_news_items(items)
        return []
