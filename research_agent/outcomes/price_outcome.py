from __future__ import annotations

from datetime import date
from typing import Dict, Iterable, Optional

import pandas as pd
from pydantic import BaseModel, Field

from research_agent.outcomes.outcome_windows import OUTCOME_WINDOWS
from research_agent.outcomes.report_manifest import ReportManifest


class WindowOutcome(BaseModel):
    window: str
    start_price: float
    start_date: str
    end_date: Optional[str] = None
    end_price: Optional[float] = None
    return_pct: Optional[float] = None
    max_gain_pct: Optional[float] = None
    max_drawdown_pct: Optional[float] = None
    hit_stop: Optional[bool] = None
    hit_target: Optional[bool] = None
    days_to_stop: Optional[int] = None
    days_to_target: Optional[int] = None


class PriceOutcomeReport(BaseModel):
    report_id: str
    ticker: str
    price_basis_date: str
    price_basis_close: float
    outcomes: Dict[str, WindowOutcome] = Field(default_factory=dict)


def calculate_forward_return(start_price: float, end_price: float) -> float:
    return (end_price / start_price) - 1


def calculate_max_gain(start_price: float, future_highs: Iterable[float]) -> float:
    return (max(future_highs) / start_price) - 1


def calculate_max_drawdown(start_price: float, future_lows: Iterable[float]) -> float:
    return (min(future_lows) / start_price) - 1


def calculate_price_outcomes(
    manifest: ReportManifest,
    price_history: pd.DataFrame,
    stop_loss: Optional[float] = None,
    target: Optional[float] = None,
    windows: Optional[dict[str, int]] = None,
) -> PriceOutcomeReport:
    windows = windows or OUTCOME_WINDOWS
    future_prices = _future_prices_only(price_history, manifest.price_basis_date)
    outcomes: dict[str, WindowOutcome] = {}
    for label, days in windows.items():
        window_prices = future_prices.head(days)
        outcomes[label] = _calculate_window_outcome(
            label=label,
            start_date=manifest.price_basis_date,
            start_price=manifest.price_basis_close,
            window_prices=window_prices,
            stop_loss=stop_loss,
            target=target,
        )
    return PriceOutcomeReport(
        report_id=manifest.report_id,
        ticker=manifest.ticker,
        price_basis_date=manifest.price_basis_date,
        price_basis_close=manifest.price_basis_close,
        outcomes=outcomes,
    )


def _calculate_window_outcome(
    label: str,
    start_date: str,
    start_price: float,
    window_prices: pd.DataFrame,
    stop_loss: Optional[float],
    target: Optional[float],
) -> WindowOutcome:
    if window_prices.empty:
        return WindowOutcome(window=label, start_price=start_price, start_date=start_date)

    end = window_prices.iloc[-1]
    highs = window_prices["high"] if "high" in window_prices else window_prices["close"]
    lows = window_prices["low"] if "low" in window_prices else window_prices["close"]

    days_to_stop = _days_to_level(window_prices, stop_loss, direction="stop") if stop_loss is not None else None
    days_to_target = _days_to_level(window_prices, target, direction="target") if target is not None else None
    return WindowOutcome(
        window=label,
        start_price=start_price,
        start_date=start_date,
        end_date=str(end["date"]),
        end_price=float(end["close"]),
        return_pct=calculate_forward_return(start_price, float(end["close"])),
        max_gain_pct=calculate_max_gain(start_price, [float(value) for value in highs]),
        max_drawdown_pct=calculate_max_drawdown(start_price, [float(value) for value in lows]),
        hit_stop=days_to_stop is not None if stop_loss is not None else None,
        hit_target=days_to_target is not None if target is not None else None,
        days_to_stop=days_to_stop,
        days_to_target=days_to_target,
    )


def _future_prices_only(price_history: pd.DataFrame, price_basis_date: str) -> pd.DataFrame:
    df = price_history.copy()
    df.columns = [str(column).strip().lower() for column in df.columns]
    if "date" not in df.columns:
        raise ValueError("price_history requires a date column.")
    df["date"] = pd.to_datetime(df["date"]).dt.date
    basis = date.fromisoformat(price_basis_date[:10])
    df = df[df["date"] > basis].sort_values("date")
    for column in ["open", "high", "low", "close"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    df["date"] = df["date"].astype(str)
    return df.reset_index(drop=True)


def _days_to_level(
    window_prices: pd.DataFrame,
    level: Optional[float],
    direction: str,
) -> Optional[int]:
    if level is None:
        return None
    for index, row in window_prices.reset_index(drop=True).iterrows():
        high = float(row["high"]) if "high" in row else float(row["close"])
        low = float(row["low"]) if "low" in row else float(row["close"])
        if direction == "stop" and low <= level:
            return index + 1
        if direction == "target" and high >= level:
            return index + 1
    return None

