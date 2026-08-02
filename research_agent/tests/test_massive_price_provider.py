import json

import pytest

from research_agent.sources.prices.massive_price_provider import MassivePriceProvider


class _Response:
    def __init__(self, payload):
        self.payload = payload

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def read(self):
        return json.dumps(self.payload).encode("utf-8")


def test_massive_provider_requires_api_key():
    with pytest.raises(ValueError):
        MassivePriceProvider("")


def test_massive_provider_normalizes_daily_ohlcv(monkeypatch):
    payload = {
        "status": "OK",
        "results": [
            {"t": 1785024000000, "o": 10, "h": 12, "l": 9, "c": 11, "v": 1234}
        ],
    }
    captured = {}

    def fake_urlopen(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        captured["authorization"] = request.get_header("Authorization")
        return _Response(payload)

    monkeypatch.setattr(
        "research_agent.sources.prices.massive_price_provider.urllib.request.urlopen",
        fake_urlopen,
    )
    provider = MassivePriceProvider("secret", base_url="https://prices.example")
    frame = provider.get_history("genr", "2026-01-01", "2026-07-26")

    assert list(frame.columns) == [
        "date",
        "open",
        "high",
        "low",
        "close",
        "volume",
        "adjusted_open",
        "adjusted_high",
        "adjusted_low",
        "adjusted_close",
    ]
    assert frame.iloc[0]["close"] == 11
    assert frame.iloc[0]["adjusted_open"] == 10
    assert frame.iloc[0]["adjusted_high"] == 12
    assert frame.iloc[0]["adjusted_low"] == 9
    assert frame.iloc[0]["adjusted_close"] == 11
    assert "/v2/aggs/ticker/GENR/range/1/day/2026-01-01/2026-07-26" in captured["url"]
    assert "adjusted=true" in captured["url"]
    assert "secret" not in captured["url"]
    assert "apiKey=" not in captured["url"]
    assert captured["authorization"] == "Bearer secret"
