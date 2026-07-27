from __future__ import annotations

import pandas as pd


def normalize_prices(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    df.columns = [str(column).strip().lower() for column in df.columns]
    if "date" not in df.columns:
        raise ValueError("Price data requires a date column.")
    df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
    for column in [
        "open", "high", "low", "close", "volume",
        "adjusted_open", "adjusted_high", "adjusted_low", "adjusted_close",
    ]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.sort_values("date").reset_index(drop=True)
