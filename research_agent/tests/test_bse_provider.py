from datetime import datetime, timezone

import pandas as pd

from research_agent.sources.bse.bse_provider import BseIssuerProvider


def _profile_html() -> str:
    timestamp = int(
        datetime(2026, 7, 23, 12, tzinfo=timezone.utc).timestamp() * 1000
    )
    return f"""
    <html><body>
      <a href="?issuer=3071">annual</a>
      <div data-datasource-config="SecurityHistoricDataSource;securityId=4042"></div>
      Full Name ANY Security Printing Company Public Limited Company by Shares
      Short name ANY PLC
      Basic Information Ticker ANY ISIN HU0000093257
      Currency of trading HUF
      <script>
      window.data = {{
        "SecurityHistoricDataSource;securityId=4042":{{
          "values":[[{timestamp},6900,7000,6850,6950,62000000,8914]]
        }}
      }};
      </script>
    </body></html>
    """


def _annual_frame() -> pd.DataFrame:
    rows = [[None, None, None] for _ in range(11)]
    rows[3] = [None, "2024 (1)", "2025 (1)"]
    rows[5] = ["Total revenues", 70_000, 71_000]
    rows[6] = ["Operating Profit (EBIT)", 10_000, 11_000]
    rows[7] = ["Profit after tax", 8_000, 8_500]
    rows[8] = ["Total assets", 50_000, 48_000]
    rows[9] = ["Shareholders equity", 18_000, 20_000]
    return pd.DataFrame(rows)


def _interim_frame() -> pd.DataFrame:
    rows = [[None] * 6 for _ in range(10)]
    rows[3] = [
        "Key P&L Figures",
        "Jan 2026 - Mar 2026 (1)",
        "Jan 2025 - Dec 2025 (1)",
        "Jan 2025 - Sep 2025 (1)",
        "Jan 2025 - Jun 2025 (1)",
        "Jan 2025 - Mar 2025 (1)",
    ]
    rows[5] = ["Net sales", 17_000, 71_000, 54_000, 38_000, 23_000]
    rows[6] = ["Operating profit (EBIT)", 3_700, 11_000, 9_000, 7_000, 5_000]
    rows[7] = ["Profit after tax", 2_600, 8_500, 7_200, 5_300, 3_900]
    return pd.DataFrame(rows)


def test_bse_provider_resolves_official_identity_and_ohlcv(monkeypatch):
    provider = BseIssuerProvider()
    monkeypatch.setattr(provider, "_fetch", lambda _url: _profile_html().encode())

    issuer = provider.resolve("ANY")
    assert issuer is not None
    assert issuer.isin == "HU0000093257"
    assert issuer.currency == "HUF"

    prices = provider.get_history("ANY", "2026-07-01", "2026-07-24")
    assert prices.to_dict("records") == [
        {
            "date": "2026-07-23",
            "open": 6900.0,
            "high": 7000.0,
            "low": 6850.0,
            "close": 6950.0,
                "volume": 8914,
                "adjusted_close": 6950.0,
                "adjusted_open": 6900.0,
                "adjusted_high": 7000.0,
                "adjusted_low": 6850.0,
                "corporate_action_count": 0,
                "series_adjustment_status": "corporate_action_adjusted",
            }
        ]


def test_bse_provider_builds_trailing_quarters_without_company_branch(monkeypatch):
    provider = BseIssuerProvider()
    monkeypatch.setattr(provider, "_fetch", lambda _url: _profile_html().encode())
    issuer = provider.resolve("ANY")
    assert issuer is not None
    frames = iter([_annual_frame(), _interim_frame()])
    monkeypatch.setattr(provider, "_read_excel", lambda _url: next(frames))

    payload = provider.build_financial_payload(
        issuer,
        as_of_date="2026-07-24",
        retrieved_at="2026-07-26T00:00:00+00:00",
    )
    revenue_quarters = [
        item["value"]
        for item in payload["metrics"]
        if item["metric_name"] == "revenue"
        and item["period_bucket"] == "quarterly"
    ]
    assert revenue_quarters == [
        15_000_000.0,
        16_000_000.0,
        17_000_000.0,
        17_000_000.0,
    ]
