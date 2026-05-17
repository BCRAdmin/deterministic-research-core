from __future__ import annotations

from abc import ABC, abstractmethod

import pandas as pd


class PriceProviderBase(ABC):
    @abstractmethod
    def get_history(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        """Return date, open, high, low, close, volume, adjusted_close(optional)."""
        raise NotImplementedError
