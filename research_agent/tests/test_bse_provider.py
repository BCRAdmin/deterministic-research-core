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
      <table>
        <tr><td>Business activity</td><td><span>ANY provides secure document and identity solutions to public administrations. Its certified production capabilities offer the highest level of secure card and document personalisation.</span></td></tr>
      </table>
      <div class="tab_content" id="cp_tab_content_5">
        <table class="news"><tbody>
          <tr><td><span>31 Jul 2026 08:15</span></td><td><a href="/future">Future publication</a></td></tr>
          <tr><td><span>03 Jul 2026 12:13</span></td><td><a href="/dividend">Final dividend announcement</a></td></tr>
          <tr><td><span>18 May 2026 18:31</span></td><td><a href="/quarter">Stable first quarter</a></td></tr>
          <tr><td><span>30 Apr 2026 08:00</span></td><td><a href="/annual">Annual Report for the year 2025</a></td></tr>
        </tbody></table>
      </div>
      <div class="tab_content" id="cp_tab_content_6"></div>
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


def test_bse_provider_builds_honest_profile_context_and_publication_snapshot(
    monkeypatch,
):
    provider = BseIssuerProvider()
    monkeypatch.setattr(provider, "_fetch", lambda _url: _profile_html().encode())
    monkeypatch.setattr(
        provider,
        "_download_best_pdf_text",
        lambda _url: """
        27 Risk management
        Foreign currency risk
        Foreign currency liabilities mainly occur from raw material purchases,
        which are hedged by receivables from export sales as a natural hedge.
        Interest rate risk
        The Group reports that potential interest rate changes could affect its
        interest expense.
        Liquidity risk
        The Group manages liquidity risk by monitoring cash flows and matching
        the maturity profiles of financial assets and liabilities.
        Credit risk
        The Group limits credit risk by dealing with creditworthy counterparties
        and obtaining collateral where appropriate.
        28 Significant events after the reporting period
        """,
    )
    issuer = provider.resolve("ANY")
    assert issuer is not None

    payload = provider.build_news_payload(
        issuer,
        as_of_date="2026-07-24",
        retrieved_at="2026-07-26T00:00:00+00:00",
    )

    assert payload["coverage_status"] == "partial"
    assert payload["window_start"] == "2026-04-30"
    assert [event["event_type"] for event in payload["events"]] == [
        "business_context",
        "risk",
        "risk",
        "risk",
        "risk",
        "dividend",
        "earnings_results",
        "filing",
    ]
    assert not any(
        character.isdigit() for character in payload["events"][0]["summary"]
    )
    assert payload["events"][0]["summary"].startswith(
        "The BSE issuer profile describes the business as follows:"
    )
    assert "highest level" not in payload["events"][0]["summary"]
    assert all(event["material"] for event in payload["events"][1:5])
    assert all(not event["material"] for event in payload["events"][5:])
    assert all(
        not any(character.isdigit() for character in event["summary"])
        for event in payload["events"][1:5]
    )
    assert all(event["date"] <= "2026-07-24" for event in payload["events"])
