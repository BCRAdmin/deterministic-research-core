import pytest

from research_agent.run_pipeline import _load_release_payload_inputs
from research_agent.run_pipeline import _exclude_reclassified_operating_income
from research_agent.reconciliation.canonical_financials import (
    CanonicalFinancials,
    CanonicalMetric,
)
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

PERIMETER_AND_TABLE_GUIDANCE_HTML = """
<html><body>
<div>Second Quarter 2026 Consolidated Results</div>
<div>The former segment successfully separated in a spin-off on June 29, 2026.</div>
<div>EPS reflects the impact of a one-time gain on deconsolidation of ExampleCo, and adjusted EPS excludes that gain.</div>
<div>Results refer to NewCo only, excluding results attributable to the separated business.</div>
<table>
  <tr><td></td><td>2Q 2026</td><td>2Q 2025</td><td>Change</td></tr>
  <tr><td>Sales</td><td>$9,719</td><td>$9,322</td><td>4%</td></tr>
  <tr><td>Organic1 Growth</td><td></td><td></td><td>4%</td></tr>
  <tr><td>Operating Income</td><td>$1,737</td><td>$1,843</td><td>(6%)</td></tr>
  <tr><td>Segment Profit1</td><td>$2,240</td><td>$2,128</td><td>5%</td></tr>
  <tr><td>Segment Margin1</td><td>23.1%</td><td>22.8%</td><td>30 bps</td></tr>
  <tr><td>Adjusted Earnings Per Share1</td><td>$4.52</td><td>$4.72</td><td>(4%)</td></tr>
</table>
<div>Second Quarter 2026 Alternative Perimeter</div>
<table>
  <tr><td></td><td>2Q 2026</td><td>2Q 2025</td><td>Change</td></tr>
  <tr><td>Sales</td><td>$5,187</td><td>$5,018</td><td>3%</td></tr>
  <tr><td>Organic1 Growth</td><td></td><td></td><td>4%</td></tr>
  <tr><td>Segment Margin1</td><td>19.0%</td><td>18.0%</td><td>100 bps</td></tr>
  <tr><td>Adjusted Earnings Per Share1</td><td>$1.95</td><td>$1.77</td><td>10%</td></tr>
</table>
<table>
  <tr><td>BUILDING AUTOMATION</td><td>2Q 2026</td><td>2Q 2025</td><td>Change</td></tr>
  <tr><td>Organic1 Growth</td><td></td><td></td><td>9%</td></tr>
  <tr><td>PROCESS AUTOMATION AND TECHNOLOGY</td><td></td><td></td><td></td></tr>
  <tr><td>Organic1 Growth</td><td></td><td></td><td>(1%)</td></tr>
  <tr><td>INDUSTRIAL AUTOMATION</td><td></td><td></td><td></td></tr>
  <tr><td>Organic1 Growth</td><td></td><td></td><td>4%</td></tr>
</table>
<div>Full-Year 2026 Guidance</div>
<table>
  <tr><td></td><td>Previous Guidance</td><td>Current Guidance</td></tr>
  <tr><td>Sales</td><td>$19.9B - $20.2B</td><td>$19.8B - $20.0B</td></tr>
  <tr><td>Organic Growth</td><td>2% - 3%</td><td>3% - 4%</td></tr>
  <tr><td>Segment Margin2</td><td>19.8% - 20.3%</td><td>20.1% - 20.5%</td></tr>
  <tr><td>Adjusted Earnings Per Share2,3</td><td>$7.90 - $8.30</td><td>$8.05 - $8.35</td></tr>
</table>
</body></html>
"""


def test_selects_one_item_202_results_exhibit_from_duplicate_links():
    primary = """
    <a href="q2-results.htm">99.1</a>
    <a href="q2-results.htm">Press release with quarterly results</a>
    <a href="q2-infographic.htm">99.2</a>
    <a href="q2-infographic.htm">Infographic relating to the financial results</a>
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


def test_builds_first_consolidated_summary_segments_and_current_guidance():
    payload = build_sec_results_release_payload(
        ticker="GENR",
        cik="123456",
        accession_number="0000123456-26-000014",
        filing_date="2026-07-23",
        exhibit_document="q2-results.htm",
        html=PERIMETER_AND_TABLE_GUIDANCE_HTML,
        expected_fiscal_year=2026,
        expected_fiscal_period="Q2",
        period_end_date="2026-06-30",
        retrieved_at="2026-07-23T12:00:00Z",
    )

    metrics = {item["metric_name"]: item for item in payload["metrics"]}
    assert metrics["reported_sales_growth"]["value"] == pytest.approx(0.04)
    assert metrics["organic_sales_growth"]["value"] == pytest.approx(0.04)
    assert metrics["current_period_segment_margin"]["value"] == pytest.approx(0.231)
    assert metrics["current_period_segment_margin_change_yoy"]["value"] == pytest.approx(0.003)
    assert metrics["adjusted_eps_diluted"]["value"] == pytest.approx(4.52)
    assert metrics["adjusted_eps_growth_yoy"]["value"] == pytest.approx(-0.04)
    assert metrics["segment_organic_sales_growth_building_automation"]["value"] == pytest.approx(0.09)
    assert metrics["segment_organic_sales_growth_process_automation_and_technology"]["value"] == pytest.approx(-0.01)
    assert metrics["guidance_revenue_low"]["value"] == pytest.approx(19_800_000_000)
    assert metrics["guidance_revenue_high"]["value"] == pytest.approx(20_000_000_000)
    assert metrics["guidance_organic_sales_growth_low"]["value"] == pytest.approx(0.03)
    assert metrics["guidance_organic_sales_growth_high"]["value"] == pytest.approx(0.04)
    assert metrics["guidance_segment_margin_low"]["value"] == pytest.approx(0.201)
    assert metrics["guidance_segment_margin_high"]["value"] == pytest.approx(0.205)
    assert metrics["guidance_adjusted_eps_low"]["value"] == pytest.approx(8.05)
    assert metrics["guidance_adjusted_eps_high"]["value"] == pytest.approx(8.35)
    assert "organic-sales growth" not in metrics["adjusted_eps_diluted"]["statement"]
    assert payload["result_contract"]["operating_metric_count"] == 9
    assert payload["result_contract"]["guidance_metric_count"] == 8
    assert payload["result_contract"]["companyfacts_controls"] == {
        "current_quarter_revenue": 9719.0,
        "current_quarter_operating_income": 1737.0,
        "current_quarter_segment_profit": 2240.0,
    }


def test_builds_nonrecurring_gain_and_continuing_perimeter_context():
    payload = build_sec_results_release_payload(
        ticker="GENR",
        cik="123456",
        accession_number="0000123456-26-000014",
        filing_date="2026-07-23",
        exhibit_document="q2-results.htm",
        html=PERIMETER_AND_TABLE_GUIDANCE_HTML,
        expected_fiscal_year=2026,
        expected_fiscal_period="Q2",
        period_end_date="2026-06-30",
        retrieved_at="2026-07-23T12:00:00Z",
    )

    summaries = {event["summary"] for event in payload["events"]}
    assert any("one-time gain" in summary and "ExampleCo" in summary for summary in summaries)
    assert any("continuing-company perimeter" in summary for summary in summaries)
    action = next(event for event in payload["events"] if event["event_type"] == "corporate_action")
    assert action["date"] == "2026-06-29"


def test_builds_labeled_outlook_bullets_without_rebuilding_gaap_statements():
    html = """
    <html><body>
      <div>LOWE'S REPORTS FIRST QUARTER 2026 SALES AND EARNINGS RESULTS</div>
      <div>Comparable sales for the quarter increased 0.6%.</div>
      <div>Adjusted diluted EPS1 increased 3.8% to $3.03.</div>
      <div>Full Year 2026 Outlook</div>
      <div>• Total sales of $92.0 to 94.0 billion or an increase of approximately 7% to 9%</div>
      <div>• Comparable sales expected to be flat to up 2%</div>
      <div>• Operating income as a percentage of sales (operating margin) of 11.2% to 11.4%</div>
      <div>• Adjusted operating income as a percentage of sales (adjusted operating margin) of 11.6% to 11.8%</div>
      <div>• Diluted earnings per share of approximately $11.75 to $12.25</div>
      <div>• Adjusted diluted earnings per share of approximately $12.25 to $12.75</div>
      <div>A conference call will follow.</div>
    </body></html>
    """

    payload = build_sec_results_release_payload(
        ticker="GENR",
        cik="123456",
        accession_number="0000123456-26-000011",
        filing_date="2026-05-20",
        exhibit_document="q1-results.htm",
        html=html,
        expected_fiscal_year=2026,
        expected_fiscal_period="Q1",
        period_end_date="2026-05-01",
        retrieved_at="2026-05-20T12:00:00Z",
    )

    metrics = {item["metric_name"]: item for item in payload["metrics"]}
    assert metrics["comparable_sales_growth"]["value"] == pytest.approx(0.006)
    assert metrics["adjusted_eps_diluted"]["value"] == pytest.approx(3.03)
    assert metrics["adjusted_eps_growth_yoy"]["value"] == pytest.approx(0.038)
    assert metrics["guidance_revenue_low"]["value"] == 92_000_000_000.0
    assert metrics["guidance_revenue_high"]["value"] == 94_000_000_000.0
    assert metrics["guidance_reported_sales_growth_low"]["value"] == pytest.approx(0.07)
    assert metrics["guidance_reported_sales_growth_high"]["value"] == pytest.approx(0.09)
    assert metrics["guidance_comparable_sales_growth_low"]["value"] == 0.0
    assert metrics["guidance_comparable_sales_growth_high"]["value"] == pytest.approx(0.02)
    assert metrics["guidance_operating_margin_low"]["basis"] == "gaap"
    assert metrics["guidance_adjusted_operating_margin_high"]["basis"] == "non_gaap"
    assert metrics["guidance_eps_diluted_low"]["value"] == pytest.approx(11.75)
    assert metrics["guidance_adjusted_eps_high"]["value"] == pytest.approx(12.75)


def _quarterly_metric(metric_name, value):
    return CanonicalMetric(
        metric_name=metric_name,
        value=value,
        unit="usd",
        period="CY2026Q2",
        fiscal_year=2026,
        fiscal_period="Q2",
        period_bucket="quarterly",
        start_date="2026-04-01",
        end_date="2026-06-30",
        duration_days=90,
        source_concept=f"us-gaap:{metric_name}",
        statement_type="income_statement",
        source_ids=["SEC_TEST"],
        evidence_ids=[f"E_{metric_name}"],
        confidence="high",
    )


def _control_payload():
    return {
        "result_contract": {
            "period_end_date": "2026-06-30",
            "companyfacts_controls": {
                "current_quarter_revenue": 9719.0,
                "current_quarter_operating_income": 1737.0,
                "current_quarter_segment_profit": 2240.0,
            },
        }
    }


def test_excludes_companyfacts_operating_income_proven_to_be_segment_profit():
    canonical = CanonicalFinancials(
        ticker="GENR",
        as_of_date="2026-08-03",
        metrics=[
            _quarterly_metric("revenue", 9_719_000_000.0),
            _quarterly_metric("operating_income", 2_240_000_000.0),
        ],
    )
    sec_metrics = {
        "operating_income_latest_annual": 8_127_000_000.0,
        "operating_income_latest_4_quarters": [2_240_000_000.0],
        "quarterly": {"operating_income": [2_240_000_000.0]},
    }
    warnings = []

    assert _exclude_reclassified_operating_income(
        canonical_financials=canonical,
        sec_metrics=sec_metrics,
        evidence_items=[],
        results_release_payload=_control_payload(),
        warnings=warnings,
    )
    assert not canonical.metrics_for("operating_income")
    assert not any(key.startswith("operating_income_") for key in sec_metrics)
    assert "operating_income" not in sec_metrics["quarterly"]
    assert warnings[0]["code"] == "SEC_OPERATING_INCOME_CONTEXT_MISMATCH_EXCLUDED"


def test_keeps_companyfacts_operating_income_when_it_matches_reported_income():
    canonical = CanonicalFinancials(
        ticker="GENR",
        as_of_date="2026-08-03",
        metrics=[
            _quarterly_metric("revenue", 9_719_000_000.0),
            _quarterly_metric("operating_income", 1_737_000_000.0),
        ],
    )
    sec_metrics = {"quarterly": {"operating_income": [1_737_000_000.0]}}
    warnings = []

    assert not _exclude_reclassified_operating_income(
        canonical_financials=canonical,
        sec_metrics=sec_metrics,
        evidence_items=[],
        results_release_payload=_control_payload(),
        warnings=warnings,
    )
    assert canonical.metrics_for("operating_income")
    assert not warnings


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
