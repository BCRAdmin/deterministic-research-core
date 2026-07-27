import gzip
import json

from research_agent.sources.prices.nasdaq_price_provider import NasdaqPriceProvider


class _Response:
    def __init__(self, payload, *, compressed=False):
        raw = json.dumps(payload).encode("utf-8")
        self.raw = gzip.compress(raw) if compressed else raw
        self.headers = {"Content-Encoding": "gzip"} if compressed else {}

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return self.raw


def test_nasdaq_provider_normalizes_official_historical_rows(monkeypatch):
    payload = {
        "status": {"rCode": 200},
        "data": {
            "tradesTable": {
                "rows": [
                    {
                        "date": "07/24/2026",
                        "close": "$22.53",
                        "volume": "14,526,490",
                        "open": "$23.26",
                        "high": "$23.75",
                        "low": "$22.35",
                    },
                    {
                        "date": "07/23/2026",
                        "close": "$23.86",
                        "volume": "24,200,580",
                        "open": "$23.36",
                        "high": "$25.17",
                        "low": "$23.295",
                    },
                ]
            }
        },
    }
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["referer"] = request.get_header("Referer")
        return _Response(payload, compressed=True)

    monkeypatch.setattr(
        "research_agent.sources.prices.nasdaq_price_provider.urllib.request.urlopen",
        fake_urlopen,
    )
    provider = NasdaqPriceProvider(base_url="https://prices.example")
    frame = provider.get_history("riot", "2025-01-20", "2026-07-24")

    assert list(frame.columns) == ["date", "open", "high", "low", "close", "volume"]
    assert list(frame["date"]) == ["2026-07-23", "2026-07-24"]
    assert frame.iloc[-1]["close"] == 22.53
    assert frame.iloc[-1]["volume"] == 14_526_490
    assert "fromdate=2025-01-20" in captured["url"]
    assert "todate=2026-07-24" in captured["url"]
    assert captured["referer"].endswith("/riot/historical")
    assert provider.source_type == "exchange_ohlcv"


def test_nasdaq_provider_skips_unusable_rows(monkeypatch):
    payload = {
        "status": {"rCode": 200},
        "data": {
            "tradesTable": {
                "rows": [
                    {
                        "date": "07/24/2026",
                        "close": "N/A",
                        "volume": "1",
                        "open": "$1",
                        "high": "$1",
                        "low": "$1",
                    },
                    {
                        "date": "07/23/2026",
                        "close": "$2",
                        "volume": "2",
                        "open": "$2",
                        "high": "$2",
                        "low": "$2",
                    },
                ]
            }
        },
    }
    monkeypatch.setattr(
        "research_agent.sources.prices.nasdaq_price_provider.urllib.request.urlopen",
        lambda request, timeout: _Response(payload),
    )
    frame = NasdaqPriceProvider().get_history(
        "RIOT", "2026-07-01", "2026-07-24"
    )
    assert list(frame["date"]) == ["2026-07-23"]
