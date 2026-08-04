import pytest

from research_agent.run_pipeline import _load_release_payload_inputs
from research_agent.sources.sec.sec_results_release import (
    build_sec_results_release_payload,
    select_sec_results_exhibit,
)


RESULT_HTML = """
<html><body>
<div>Second Quarter 2026 Results</div>
<div>GAAP EPS decreased 5% to $0.86; Base Business EPS increased 8% to $0.99</div>
<div>GAAP Gross profit margin and Base Business Gross profit margin increased 140 basis points to 61.5%</div>
<div>The Company's leadership in toothpaste continued with its global market share at 41.3% year to date</div>
<div>The Company's leadership in manual toothbrushes continued with its global market share at 32.7% year to date</div>
<table>
  <tr><td></td><td>Organic Sales</td><td>Organic Volume</td><td>Pricing</td></tr>
  <tr><td>North America</td><td>-3.0%</td><td>-3.9%</td><td>+0.9%</td></tr>
  <tr><td>Latin America</td><td>+5.3%</td><td>+2.6%</td><td>+2.8%</td></tr>
  <tr><td>Total Company</td><td>+2.4%</td><td>+0.8%</td><td>+1.6%</td></tr>
</table>
<div>Full Year 2026 Guidance</div>
<div>The Company expects net sales to be up 2% to 6%.</div>
<div>The Company expects organic sales growth to be 1% to 4%.</div>
<div>On a GAAP basis, the Company expects gross profit margin to be roughly flat and double-digit earnings per share growth.</div>
</body></html>
"""

KMB_STYLE_RESULT_HTML = """
<html><body>
<div>Kimberly-Clark Announces First Quarter 2026 Results, Reaffirms 2026 Outlook</div>
<div>Gross margin was 36.8 percent compared to 37.2 percent in the prior year.</div>
<div>Adjusted gross margin was 37.9 percent, down 60 basis points versus the prior year.</div>
<div>Adjusted EPS from continuing operations were $1.60, down 1.2 percent versus the prior year.</div>
<div>Adjusted EPS attributable to Kimberly-Clark were $1.97, up 2.1 percent.</div>
<table>
  <tr><td>Q1 change vs year ago (%)</td><td>Volume</td><td>Mix/Other</td><td>Net Price</td><td>Divestitures and Business Exits(c)</td><td>Currency Translation</td><td>Total(a)</td><td>Organic(b)</td></tr>
  <tr><td>Consolidated</td><td>2.6</td><td>0.4</td><td>(0.5)</td><td>(1.8)</td><td>2.0</td><td>2.7</td><td>2.5</td></tr>
  <tr><td>NA</td><td>1.9</td><td>(0.2)</td><td>0.0</td><td>(2.7)</td><td>0.3</td><td>(0.6)</td><td>1.8</td></tr>
  <tr><td>IPC</td><td>4.1</td><td>1.4</td><td>(1.5)</td><td>0.0</td><td>5.2</td><td>9.1</td><td>4.0</td></tr>
</table>
<div>2026 Outlook</div>
<div>Adjusted Operating Profit is expected to grow at a mid-to-high single-digit rate on a constant-currency basis.</div>
<div>Adjusted Earnings Per Share from Continuing Operations are expected to grow at a double-digit rate on a constant-currency basis.</div>
</body></html>
"""


def test_selects_one_item_202_results_exhibit_from_duplicate_links():
    primary = """
    <a href="q2-results.htm">99.1</a>
    <a href="q2-results.htm">Press release with quarterly results</a>
    <a href="main-document.htm">Inline XBRL document</a>
    """

    assert select_sec_results_exhibit(primary) == "q2-results.htm"


def test_builds_company_operating_segment_and_guidance_inputs():
    payload = build_sec_results_release_payload(
        ticker="GENR",
        cik="123456",
        accession_number="0000123456-26-000011",
        filing_date="2026-07-20",
        exhibit_document="q2-results.htm",
        html=RESULT_HTML,
        expected_fiscal_year=2026,
        expected_fiscal_period="Q2",
        period_end_date="2026-06-30",
        retrieved_at="2026-07-20T12:00:00Z",
    )

    values = {item["metric_name"]: item["value"] for item in payload["metrics"]}
    assert values["organic_sales_growth"] == pytest.approx(0.024)
    assert values["organic_volume_growth"] == pytest.approx(0.008)
    assert values["pricing_growth"] == pytest.approx(0.016)
    assert values["segment_organic_sales_growth_north_america"] == pytest.approx(-0.03)
    assert values["segment_organic_sales_growth_latin_america"] == pytest.approx(0.053)
    assert values["guidance_net_sales_growth_low"] == pytest.approx(0.02)
    assert values["guidance_net_sales_growth_high"] == pytest.approx(0.06)
    assert values["guidance_organic_sales_growth_low"] == pytest.approx(0.01)
    assert values["guidance_organic_sales_growth_high"] == pytest.approx(0.04)
    assert values["current_period_gross_margin"] == pytest.approx(0.615)
    assert values["current_period_gross_margin_change_yoy"] == pytest.approx(0.014)
    assert values["adjusted_gross_margin"] == pytest.approx(0.615)
    assert values["adjusted_eps_diluted"] == pytest.approx(0.99)
    assert values["adjusted_eps_growth_yoy"] == pytest.approx(0.08)
    assert values["market_share_toothpaste"] == pytest.approx(0.413)
    assert values["market_share_manual_toothbrushes"] == pytest.approx(0.327)
    assert payload["result_contract"]["gaap_basis"] == "matching_companyfacts_filing"

    fundamentals, evidence, canonical = _load_release_payload_inputs("GENR", payload)
    assert fundamentals["latest_quarter"] == "FY2026_Q2"
    assert len(evidence) == len(payload["metrics"])
    assert {item.metric_name for item in canonical} == set(values)


def test_builds_percent_header_bridge_and_value_first_adjusted_results():
    payload = build_sec_results_release_payload(
        ticker="GENR",
        cik="123456",
        accession_number="0000123456-26-000012",
        filing_date="2026-04-28",
        exhibit_document="q1-results.htm",
        html=KMB_STYLE_RESULT_HTML,
        expected_fiscal_year=2026,
        expected_fiscal_period="Q1",
        period_end_date="2026-03-31",
        retrieved_at="2026-04-28T12:00:00Z",
    )

    values = {item["metric_name"]: item["value"] for item in payload["metrics"]}
    assert values["organic_sales_growth"] == pytest.approx(0.025)
    assert values["volume_growth"] == pytest.approx(0.026)
    assert values["pricing_growth"] == pytest.approx(-0.005)
    assert values["mix_other_impact"] == pytest.approx(0.004)
    assert values["business_portfolio_impact"] == pytest.approx(-0.018)
    assert values["foreign_exchange_impact"] == pytest.approx(0.02)
    assert values["reported_sales_growth"] == pytest.approx(0.027)
    assert values["segment_organic_sales_growth_na"] == pytest.approx(0.018)
    assert values["segment_organic_sales_growth_ipc"] == pytest.approx(0.04)
    assert values["current_period_gross_margin"] == pytest.approx(0.368)
    assert values["current_period_gross_margin_change_yoy"] == pytest.approx(-0.004)
    assert values["adjusted_gross_margin"] == pytest.approx(0.379)
    assert values["adjusted_gross_margin_change_yoy"] == pytest.approx(-0.006)
    assert values["adjusted_eps_diluted"] == pytest.approx(1.60)
    assert values["adjusted_eps_growth_yoy"] == pytest.approx(-0.012)
    summaries = {event["summary"] for event in payload["events"]}
    assert any("operating profit" in summary for summary in summaries)
    assert any("continuing-operations EPS" in summary for summary in summaries)


def test_does_not_treat_bare_numbers_as_percent_without_table_unit_context():
    html = """
    <div>First Quarter 2026 Results</div>
    <table>
      <tr><td></td><td>Volume</td><td>Net Price</td></tr>
      <tr><td>Consolidated</td><td>2.6</td><td>(0.5)</td></tr>
    </table>
    """
    with pytest.raises(ValueError, match="keine ausreichend strukturierte"):
        build_sec_results_release_payload(
            ticker="GENR",
            cik="123456",
            accession_number="0000123456-26-000013",
            filing_date="2026-04-28",
            exhibit_document="q1-results.htm",
            html=html,
            expected_fiscal_year=2026,
            expected_fiscal_period="Q1",
            period_end_date="2026-03-31",
            retrieved_at="2026-04-28T12:00:00Z",
        )


@pytest.mark.parametrize(
    ("expected_period", "html", "message"),
    [
        ("Q3", RESULT_HTML, "stimmt nicht"),
        (
            "Q2",
            "<div>Second Quarter 2026 Results</div><table><tr><td>Organic Sales Growth</td><td>2.4%</td></tr></table>",
            "keine ausreichend strukturierte",
        ),
    ],
)
def test_rejects_mismatched_or_structurally_thin_results(
    expected_period,
    html,
    message,
):
    with pytest.raises(ValueError, match=message):
        build_sec_results_release_payload(
            ticker="GENR",
            cik="123456",
            accession_number="0000123456-26-000011",
            filing_date="2026-07-20",
            exhibit_document="q2-results.htm",
            html=html,
            expected_fiscal_year=2026,
            expected_fiscal_period=expected_period,
            period_end_date="2026-06-30",
            retrieved_at="2026-07-20T12:00:00Z",
        )
