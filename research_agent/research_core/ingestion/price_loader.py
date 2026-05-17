from __future__ import annotations

from pathlib import Path
from typing import Union

import pandas as pd


def load_price_history(ticker: str, raw_dir: Union[str, Path] = "research_agent/data/raw") -> pd.DataFrame:
    path = Path(raw_dir) / f"{ticker.upper()}_prices.csv"
    if not path.exists():
        raise FileNotFoundError(f"Missing price history file: {path}")
    return pd.read_csv(path)
