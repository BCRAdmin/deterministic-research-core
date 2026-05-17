from __future__ import annotations

from abc import ABC, abstractmethod


class NewsProviderBase(ABC):
    @abstractmethod
    def get_news(self, ticker: str, start: str, end: str) -> list[dict]:
        raise NotImplementedError
