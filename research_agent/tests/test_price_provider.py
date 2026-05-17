from research_agent.sources.prices.csv_price_provider import CsvPriceProvider


def test_csv_price_provider_returns_normalized_ohlcv(tmp_path):
    price_dir = tmp_path / "prices"
    price_dir.mkdir()
    (price_dir / "MDB.csv").write_text(
        "date,open,high,low,close,volume,adj_close\n"
        "2026-04-01,240,245,235,242,1000000,242\n"
        "2026-05-01,250,255,248,253,1200000,253\n",
        encoding="utf-8",
    )

    provider = CsvPriceProvider(price_dir)
    df = provider.get_history("MDB", "2026-04-01", "2026-05-01")

    assert {"date", "open", "high", "low", "close", "volume"}.issubset(df.columns)
    assert "adjusted_close" in df.columns
    assert list(df["date"]) == ["2026-04-01", "2026-05-01"]
