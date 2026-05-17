from __future__ import annotations

import pandas as pd


REQUIRED_OHLCV_COLUMNS = {"date", "open", "high", "low", "close", "volume"}


def normalize_ohlcv(df: pd.DataFrame) -> pd.DataFrame:
    normalized = df.copy()
    normalized.columns = [str(column).strip().lower().replace(" ", "_") for column in normalized.columns]
    if "adj_close" in normalized.columns and "adjusted_close" not in normalized.columns:
        normalized = normalized.rename(columns={"adj_close": "adjusted_close"})
    missing = REQUIRED_OHLCV_COLUMNS - set(normalized.columns)
    if missing:
        raise ValueError(f"Price data missing required columns: {sorted(missing)}")
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.strftime("%Y-%m-%d")
    for column in ["open", "high", "low", "close", "volume", "adjusted_close"]:
        if column in normalized.columns:
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
    return normalized.sort_values("date").reset_index(drop=True)
