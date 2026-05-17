import pandas as pd

from research_agent.research_core.calculations.technicals import (
    atr,
    bollinger_bands,
    calculate_technical_metrics,
    ema,
    macd,
    rsi_wilder,
    sma,
)


def _sample_ohlcv(rows=220):
    dates = pd.date_range("2025-01-01", periods=rows, freq="D")
    closes = [100 + index * 0.5 + ((index % 7) - 3) for index in range(rows)]
    return pd.DataFrame(
        {
            "date": dates.strftime("%Y-%m-%d"),
            "open": [close - 0.5 for close in closes],
            "high": [close + 2 for close in closes],
            "low": [close - 2 for close in closes],
            "close": closes,
            "volume": [1_000_000 + index * 1000 for index in range(rows)],
        }
    )


def test_sma_uses_full_window_before_value():
    series = pd.Series([1, 2, 3, 4, 5])
    result = sma(series, 3)
    assert pd.isna(result.iloc[1])
    assert result.iloc[-1] == 4


def test_ema_macd_bollinger_atr_return_expected_shapes():
    df = _sample_ohlcv(60)
    close = df["close"]

    assert len(ema(close, 10)) == 60
    assert set(macd(close).columns) == {"macd", "macd_signal", "macd_histogram"}
    assert set(bollinger_bands(close).columns) == {
        "bollinger_mid",
        "bollinger_upper",
        "bollinger_lower",
    }
    assert len(atr(df)) == 60


def test_calculate_technical_metrics_includes_required_signals():
    metrics = calculate_technical_metrics(_sample_ohlcv())

    assert metrics.sma_10 is not None
    assert metrics.sma_20 is not None
    assert metrics.sma_50 is not None
    assert metrics.sma_200 is not None
    assert metrics.ema_10 is not None
    assert metrics.ema_20 is not None
    assert metrics.avg_volume_20 is not None
    assert metrics.signals["rsi_zone"] in {"oversold", "neutral", "overbought", "unavailable"}
    assert "price_distance_pct" in metrics.signals


def test_rsi_wilder_stays_in_indicator_bounds_for_mixed_series():
    close = pd.Series([10, 11, 10, 12, 13, 12, 14, 13, 15, 16, 15, 17, 18, 17, 19, 20])
    latest = rsi_wilder(close).dropna().iloc[-1]
    assert 0 <= latest <= 100

