from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class PriceProviderBase(ABC):
    @abstractmethod
    def get_history(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Return raw OHLCV and, only when verified, a complete adjusted OHLC set."""
        raise NotImplementedError
