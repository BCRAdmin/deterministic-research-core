from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from research_agent.research_core.models.data_packet import DataPacket
from research_agent.research_core.models.metrics_packet import TechnicalMetrics


def sma(series: pd.Series, window: int) -> pd.Series:
    return series.rolling(window=window, min_periods=window).mean()


def ema(series: pd.Series, span: int) -> pd.Series:
    return series.ewm(span=span, adjust=False).mean()


def rsi_wilder(close: pd.Series, period: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)

    avg_gain = gain.ewm(alpha=1 / period, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / period, adjust=False).mean()

    rs = avg_gain / avg_loss.replace(0, np.nan)
    return 100 - (100 / (1 + rs))


def macd(close: pd.Series, fast: int = 12, slow: int = 26, signal: int = 9) -> pd.DataFrame:
    ema_fast = ema(close, fast)
    ema_slow = ema(close, slow)
    macd_line = ema_fast - ema_slow
    signal_line = ema(macd_line, signal)
    hist = macd_line - signal_line

    return pd.DataFrame(
        {
            "macd": macd_line,
            "macd_signal": signal_line,
            "macd_histogram": hist,
        }
    )


def bollinger_bands(close: pd.Series, window: int = 20, num_std: float = 2.0) -> pd.DataFrame:
    mid = sma(close, window)
    std = close.rolling(window=window, min_periods=window).std()

    return pd.DataFrame(
        {
            "bollinger_mid": mid,
            "bollinger_upper": mid + num_std * std,
            "bollinger_lower": mid - num_std * std,
        }
    )


def atr(df: pd.DataFrame, period: int = 14) -> pd.Series:
    high = df["high"]
    low = df["low"]
    close = df["close"]

    prev_close = close.shift(1)

    tr = pd.concat(
        [
            high - low,
            (high - prev_close).abs(),
            (low - prev_close).abs(),
        ],
        axis=1,
    ).max(axis=1)

    return tr.ewm(alpha=1 / period, adjust=False).mean()


def average_volume(volume: pd.Series, window: int = 20) -> pd.Series:
    return volume.rolling(window=window, min_periods=window).mean()


def price_distance_pct(price: float, reference: Optional[float]) -> Optional[float]:
    if reference is None or reference == 0 or _is_missing(reference):
        return None
    return (price - reference) / reference


def calculate_technical_metrics(
    ohlcv: pd.DataFrame,
    data_packet: Optional[DataPacket] = None,
    indicator_date: Optional[str] = None,
) -> TechnicalMetrics:
    df = _prepare_ohlcv(ohlcv)
    if df.empty:
        raise ValueError("OHLCV data is empty.")

    close = df["close"]
    indicators = pd.DataFrame(index=df.index)
    indicators["sma_10"] = sma(close, 10)
    indicators["sma_20"] = sma(close, 20)
    indicators["sma_50"] = sma(close, 50)
    indicators["sma_200"] = sma(close, 200)
    indicators["ema_10"] = ema(close, 10)
    indicators["ema_20"] = ema(close, 20)
    indicators["rsi_14"] = rsi_wilder(close, 14)
    indicators = indicators.join(macd(close))
    indicators = indicators.join(bollinger_bands(close))
    indicators["atr_14"] = atr(df, 14)
    indicators["avg_volume_20"] = average_volume(df["volume"], 20)

    latest = indicators.iloc[-1]
    latest_close = float(close.iloc[-1])
    latest_date = indicator_date or _extract_latest_date(df, data_packet)

    values = {key: _clean_number(latest.get(key)) for key in indicators.columns}
    distances = {
        "distance_to_sma_10_pct": price_distance_pct(latest_close, values["sma_10"]),
        "distance_to_sma_20_pct": price_distance_pct(latest_close, values["sma_20"]),
        "distance_to_sma_50_pct": price_distance_pct(latest_close, values["sma_50"]),
        "distance_to_sma_200_pct": price_distance_pct(latest_close, values["sma_200"]),
        "distance_to_ema_10_pct": price_distance_pct(latest_close, values["ema_10"]),
        "distance_to_ema_20_pct": price_distance_pct(latest_close, values["ema_20"]),
    }

    signals = build_technical_signals(latest_close, values)
    signals["price_distance_pct"] = {
        key.replace("distance_to_", ""): value for key, value in distances.items()
    }

    return TechnicalMetrics(
        indicator_date=latest_date,
        close=latest_close,
        **values,
        **distances,
        signals=signals,
    )


def build_technical_signals(close: float, values: dict[str, Optional[float]]) -> dict[str, object]:
    return {
        "price_below_ema_10": _is_below(close, values.get("ema_10")),
        "price_below_ema_20": _is_below(close, values.get("ema_20")),
        "price_below_sma_50": _is_below(close, values.get("sma_50")),
        "price_below_sma_200": _is_below(close, values.get("sma_200")),
        "death_cross": _death_cross(values.get("sma_50"), values.get("sma_200")),
        "rsi_zone": _rsi_zone(values.get("rsi_14")),
        "macd_momentum": _macd_momentum(values.get("macd"), values.get("macd_signal"), values.get("macd_histogram")),
    }


def _prepare_ohlcv(ohlcv: pd.DataFrame) -> pd.DataFrame:
    df = ohlcv.copy()
    df.columns = [str(column).strip().lower() for column in df.columns]
    required = {"high", "low", "close", "volume"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"OHLCV data missing required columns: {sorted(missing)}")
    if "date" in df.columns:
        df["date"] = pd.to_datetime(df["date"]).dt.strftime("%Y-%m-%d")
        df = df.sort_values("date")
    for column in ["open", "high", "low", "close", "volume"]:
        if column in df.columns:
            df[column] = pd.to_numeric(df[column], errors="coerce")
    return df.reset_index(drop=True)


def _extract_latest_date(df: pd.DataFrame, data_packet: Optional[DataPacket]) -> str:
    if "date" in df.columns:
        return str(df["date"].iloc[-1])
    if data_packet is not None:
        return data_packet.price_basis.date
    raise ValueError("indicator_date is required when OHLCV data has no date column.")


def _clean_number(value: object) -> Optional[float]:
    if _is_missing(value):
        return None
    return float(value)


def _is_missing(value: object) -> bool:
    try:
        return value is None or bool(pd.isna(value))
    except TypeError:
        return value is None


def _is_below(price: float, reference: Optional[float]) -> bool:
    return reference is not None and not _is_missing(reference) and price < reference


def _death_cross(sma_50: Optional[float], sma_200: Optional[float]) -> bool:
    return (
        sma_50 is not None
        and sma_200 is not None
        and not _is_missing(sma_50)
        and not _is_missing(sma_200)
        and sma_50 < sma_200
    )


def _rsi_zone(value: Optional[float]) -> str:
    if value is None or _is_missing(value):
        return "unavailable"
    if value >= 70:
        return "overbought"
    if value <= 30:
        return "oversold"
    return "neutral"


def _macd_momentum(
    macd_value: Optional[float],
    signal_value: Optional[float],
    histogram: Optional[float],
) -> str:
    if any(value is None or _is_missing(value) for value in [macd_value, signal_value, histogram]):
        return "unavailable"
    if macd_value >= 0 and histogram >= 0:
        return "positive"
    if macd_value < 0 and histogram > 0:
        return "improving_but_negative"
    if macd_value < 0 and histogram <= 0:
        return "negative"
    return "weakening_but_positive"

