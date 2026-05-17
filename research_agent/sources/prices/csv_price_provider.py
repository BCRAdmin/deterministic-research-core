from __future__ import annotations

from pathlib import Path
from typing import Union

import pandas as pd

from research_agent.sources.prices.price_normalizer import normalize_ohlcv
from research_agent.sources.prices.price_provider_base import PriceProviderBase


class CsvPriceProvider(PriceProviderBase):
    def __init__(self, base_dir: Union[str, Path]):
        self.base_dir = Path(base_dir)

    def get_history(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        path = self.base_dir / f"{ticker.upper()}.csv"
        if not path.exists():
            path = self.base_dir / f"{ticker}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing CSV price history: {path}")
        df = normalize_ohlcv(pd.read_csv(path))
        start_ts = pd.to_datetime(start)
        end_ts = pd.to_datetime(end)
        dates = pd.to_datetime(df["date"])
        mask = (dates >= start_ts) & (dates <= end_ts)
        return df.loc[mask].sort_values("date").reset_index(drop=True)
