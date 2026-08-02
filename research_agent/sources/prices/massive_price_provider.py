from __future__ import annotations

import json
import urllib.parse
import urllib.request
from datetime import datetime, timezone

import pandas as pd

from research_agent.sources.prices.price_provider_base import PriceProviderBase


class MassivePriceProvider(PriceProviderBase):
    """Daily SIP-derived OHLCV from the Massive/Polygon aggregates API."""

    source_type = "trusted_market_data_vendor"
    source_url = "https://api.massive.com/v2/aggs"

    def __init__(
        self,
        api_key: str,
        *,
        base_url: str = "https://api.massive.com",
        timeout_seconds: int = 30,
    ):
        if not api_key.strip():
            raise ValueError("Massive API key is required.")
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def get_history(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        symbol = ticker.strip().upper()
        path = f"/v2/aggs/ticker/{urllib.parse.quote(symbol)}/range/1/day/{start}/{end}"
        query = urllib.parse.urlencode(
            {
                "adjusted": "true",
                "sort": "asc",
                "limit": "50000",
            }
        )
        request = urllib.request.Request(
            f"{self.base_url}{path}?{query}",
            headers={
                "Accept": "application/json",
                "Authorization": f"Bearer {self.api_key}",
                "User-Agent": "Room16Research/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            payload = json.loads(response.read().decode("utf-8"))
        if payload.get("status") not in {"OK", "DELAYED"}:
            raise RuntimeError(
                f"Massive OHLCV request failed for {symbol}: {payload.get('status')}"
            )
        rows = [
            {
                "date": datetime.fromtimestamp(item["t"] / 1000, tz=timezone.utc)
                .date()
                .isoformat(),
                "open": float(item["o"]),
                "high": float(item["h"]),
                "low": float(item["l"]),
                "close": float(item["c"]),
                "volume": int(item["v"]),
                "adjusted_open": float(item["o"]),
                "adjusted_high": float(item["h"]),
                "adjusted_low": float(item["l"]),
                "adjusted_close": float(item["c"]),
            }
            for item in payload.get("results") or []
            if all(key in item for key in ("t", "o", "h", "l", "c", "v"))
        ]
        if not rows:
            raise RuntimeError(f"Massive returned no usable OHLCV rows for {symbol}.")
        return pd.DataFrame(rows)
