from __future__ import annotations

import gzip
import json
import re
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Literal

import pandas as pd

from research_agent.sources.prices.price_provider_base import PriceProviderBase


class NasdaqPriceProvider(PriceProviderBase):
    """Public daily OHLCV from Nasdaq's official historical-data surface."""

    provider_id = "nasdaq"
    source_type = "exchange_ohlcv"
    source_url = "https://www.nasdaq.com/market-activity/stocks"

    def __init__(
        self,
        *,
        base_url: str = "https://api.nasdaq.com",
        timeout_seconds: int = 30,
        asset_class: Literal["stocks", "etf"] = "stocks",
    ):
        if asset_class not in {"stocks", "etf"}:
            raise ValueError("Nasdaq asset class must be stocks or etf.")
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.asset_class = asset_class

    def get_history(self, ticker: str, start: str, end: str) -> pd.DataFrame:
        symbol = ticker.strip().upper()
        if not re.fullmatch(r"[A-Z0-9.-]{1,24}", symbol):
            raise ValueError("Nasdaq ticker is missing or invalid.")
        start_date = datetime.strptime(start, "%Y-%m-%d").date()
        end_date = datetime.strptime(end, "%Y-%m-%d").date()
        if start_date > end_date:
            raise ValueError("Nasdaq price range start must not be after end.")

        query = urllib.parse.urlencode(
            {
                "assetclass": self.asset_class,
                "fromdate": start_date.isoformat(),
                "todate": end_date.isoformat(),
                "limit": "5000",
            }
        )
        api_url = f"{self.base_url}/api/quote/{urllib.parse.quote(symbol)}/historical?{query}"
        request = urllib.request.Request(
            api_url,
            headers={
                "Accept": "application/json, text/plain, */*",
                "Accept-Encoding": "gzip, deflate",
                "Origin": "https://www.nasdaq.com",
                "Referer": (
                    "https://www.nasdaq.com/market-activity/"
                    f"{'etf' if self.asset_class == 'etf' else 'stocks'}/"
                    f"{symbol.lower()}/historical"
                ),
                "User-Agent": "Mozilla/5.0 Room16Research/1.0",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout_seconds) as response:
            raw = response.read()
            if str(response.headers.get("Content-Encoding") or "").lower() == "gzip":
                raw = gzip.decompress(raw)
            payload = json.loads(raw.decode("utf-8"))

        status = payload.get("status") or {}
        data = payload.get("data") or {}
        rows = (data.get("tradesTable") or {}).get("rows") or []
        if status.get("rCode") not in {None, 200} or not rows:
            messages = status.get("bCodeMessage") or []
            detail = "; ".join(str(item.get("errorMessage") or item) for item in messages)
            raise RuntimeError(
                f"Nasdaq returned no usable OHLCV rows for {symbol}"
                + (f": {detail}" if detail else ".")
            )

        normalized = []
        for item in rows:
            try:
                row_date = datetime.strptime(str(item["date"]), "%m/%d/%Y").date()
                values = {
                    key: _parse_number(item.get(key))
                    for key in ("open", "high", "low", "close", "volume")
                }
            except (KeyError, TypeError, ValueError):
                continue
            if any(value is None for value in values.values()):
                continue
            if not start_date <= row_date <= end_date:
                continue
            normalized.append(
                {
                    "date": row_date.isoformat(),
                    "open": values["open"],
                    "high": values["high"],
                    "low": values["low"],
                    "close": values["close"],
                    "volume": int(values["volume"]),
                }
            )
        if not normalized:
            raise RuntimeError(f"Nasdaq returned no usable OHLCV rows for {symbol}.")
        self.source_url = (
            "https://www.nasdaq.com/market-activity/"
            f"{'etf' if self.asset_class == 'etf' else 'stocks'}/"
            f"{symbol.lower()}/historical"
        )
        return (
            pd.DataFrame(normalized)
            .drop_duplicates(subset=["date"], keep="last")
            .sort_values("date")
            .reset_index(drop=True)
        )


def _parse_number(value: object) -> float | None:
    cleaned = re.sub(r"[^0-9.\-]", "", str(value or ""))
    if not cleaned or cleaned in {"-", ".", "-."}:
        return None
    return float(cleaned)
