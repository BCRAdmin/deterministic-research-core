import json

from research_agent.sources.sec.sec_filing_risks import SecFilingReference
from research_agent.sources.sec.sec_inline_facts import (
    build_sec_inline_debt_supplement_payload,
    build_sec_inline_fact_supplement_payload,
    load_sec_inline_fact_supplement,
    save_sec_inline_fact_supplement,
)


def _filing():
    return SecFilingReference(
        cik="1283699",
        form="10-Q",
        filing_date="2026-07-23",
        report_date="2026-06-30",
        accession_number="0001283699-26-000101",
        primary_document="tmus-20260630.htm",
        url="https://www.sec.gov/Archives/example/tmus-20260630.htm",
    )


def _companyfacts(*, with_debt=False):
    facts = {
        "Revenues": {
            "units": {
                "USD": [
                    {
                        "val": 22_790_000_000,
                        "fy": 2026,
                        "fp": "Q2",
                        "form": "10-Q",
                        "filed": "2026-07-23",
                        "start": "2026-04-01",
                        "end": "2026-06-30",
                        "accn": "0001283699-26-000101",
                    }
                ]
            }
        }
    }
    if with_debt:
        facts["LongTermDebtNoncurrent"] = {
            "units": {
                "USD": [
                    {
                        "val": 78_504_000_000,
                        "fy": 2026,
                        "fp": "Q2",
                        "form": "10-Q",
                        "filed": "2026-07-23",
                        "end": "2026-06-30",
                        "accn": "0001283699-26-000101",
                    }
                ]
            }
        }
    return {"facts": {"us-gaap": facts}}


def _html():
    return """
    <html><body>
      <xbrli:context id="current"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier><xbrli:segment></xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-06-30</xbrli:instant></xbrli:period></xbrli:context>
      <xbrli:context id="prior"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier></xbrli:entity><xbrli:period><xbrli:instant>2025-12-31</xbrli:instant></xbrli:period></xbrli:context>
      <table>
        <tr><td>Long-term debt</td><td><ix:nonFraction unitRef="usd" contextRef="current" name="us-gaap:LongTermDebtNoncurrent" scale="6">78,504</ix:nonFraction></td><td><ix:nonFraction unitRef="usd" contextRef="prior" name="us-gaap:LongTermDebtNoncurrent" scale="6">79,649</ix:nonFraction></td></tr>
        <tr><td>Long-term debt to affiliates</td><td><ix:nonFraction unitRef="usd" contextRef="current" name="us-gaap:LongTermDebtNoncurrent" format="ixt:fixed-zero" scale="6">—</ix:nonFraction></td></tr>
      </table>
      <table>
        <tr><td>Long-term debt</td><td><ix:nonFraction unitRef="usd" contextRef="current" name="us-gaap:LongTermDebtNoncurrent" scale="6">1,415</ix:nonFraction></td></tr>
      </table>
    </body></html>
    """


def test_recovers_first_current_statement_debt_and_preserves_filing_authority(tmp_path):
    payload = build_sec_inline_debt_supplement_payload(
        ticker="TMUS",
        filing=_filing(),
        html=_html(),
        companyfacts=_companyfacts(),
        retrieved_at="2026-08-03T04:00:00+00:00",
    )

    assert payload is not None
    assert payload["facts"][0]["value"] == 78_504_000_000
    path = save_sec_inline_fact_supplement(tmp_path / "TMUS.json", payload)
    facts, evidence = load_sec_inline_fact_supplement(path, ticker="TMUS")
    assert facts[0].metric_name == "debt_noncurrent"
    assert facts[0].end == "2026-06-30"
    assert evidence[0].value == 78_504_000_000
    assert evidence[0].url == _filing().url
    assert json.loads(path.read_text(encoding="utf-8"))["filing"]["form"] == "10-Q"


def test_does_not_duplicate_current_companyfacts_debt():
    assert (
        build_sec_inline_debt_supplement_payload(
            ticker="TMUS",
            filing=_filing(),
            html=_html(),
            companyfacts=_companyfacts(with_debt=True),
            retrieved_at="2026-08-03T04:00:00+00:00",
        )
        is None
    )


def test_sums_current_cover_page_stock_classes_as_economic_shares(tmp_path):
    html = _html().replace(
        "<table>",
        """
        <xbrli:context id="class-a"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassAMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-07-15</xbrli:instant></xbrli:period></xbrli:context>
        <xbrli:context id="class-b"><xbrli:entity><xbrli:identifier>1283699</xbrli:identifier><xbrli:segment><xbrldi:explicitMember dimension="us-gaap:StatementClassOfStockAxis">us-gaap:CommonClassBMember</xbrldi:explicitMember></xbrli:segment></xbrli:entity><xbrli:period><xbrli:instant>2026-07-15</xbrli:instant></xbrli:period></xbrli:context>
        <p>As of July 15, 2026, there were
          <ix:nonFraction unitRef="shares" contextRef="class-a" name="dei:EntityCommonStockSharesOutstanding" scale="0">3,539,192,198</ix:nonFraction>
          Class A shares and
          <ix:nonFraction unitRef="shares" contextRef="class-b" name="dei:EntityCommonStockSharesOutstanding" scale="0">9,444,375</ix:nonFraction>
          Class B shares outstanding.
        </p>
        <table>
        """,
        1,
    )
    payload = build_sec_inline_fact_supplement_payload(
        ticker="CMCSA",
        filing=_filing(),
        html=html,
        companyfacts=_companyfacts(with_debt=True),
        retrieved_at="2026-08-03T04:00:00+00:00",
    )

    assert payload is not None
    assert len(payload["facts"]) == 1
    assert payload["facts"][0]["metric_name"] == "economic_share_count"
    assert payload["facts"][0]["value"] == 3_548_636_573
    assert payload["facts"][0]["end"] == "2026-07-15"
    path = save_sec_inline_fact_supplement(tmp_path / "CMCSA.json", payload)
    facts, evidence = load_sec_inline_fact_supplement(path, ticker="CMCSA")
    assert facts[0].metric_name == "economic_share_count"
    assert evidence[0].supports_metrics == ["economic_share_count"]
