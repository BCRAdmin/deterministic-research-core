import pytest

from research_agent.content.claim_generator import generate_research_claims
from research_agent.content.claim_generator import (
    _event_display_statement,
    _event_catalyst_summary,
    _is_operating_catalyst_event,
)
from research_agent.decision.rating_engine import build_decision_packet
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.ingestion.news_loader import news_evidence_items
from research_agent.research_core.models.data_packet import (
    DataPacket,
    MaterialNewsEvent,
    NewsCoverage,
    PriceBasis,
)
from research_agent.research_core.models.metrics_packet import (
    FundamentalMetrics,
    MetricsPacket,
    TechnicalMetrics,
    ValuationMetrics,
)
from research_agent.research_core.models.validation_report import ValidationReport
from research_agent.sources.sec.sec_operating_kpis import (
    build_sec_operating_kpi_payload,
)


def _cost_payload():
    return build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html_documents=[
            """
            <p>Paid members were 82.9 million and cardholders were 148.5 million.</p>
            <p>Renewal rates were 92.2% in the U.S. and Canada and 89.7% worldwide.</p>
            <p>Comparable sales rose 5.7%, traffic increased 4.9%, and average ticket rose 0.8%.</p>
            <p>Digital sales increased 15.6%.</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )


def test_operating_kpi_extractor_creates_numeric_primary_evidence() -> None:
    payload = _cost_payload()
    evidence = news_evidence_items("TEST", payload["events"])

    assert payload["all_kpis_dispositioned"] is True
    assert any(
        item["status"] == "found" and item["kpi_id"] == "paid_members"
        for item in payload["kpi_dispositions"]
    )
    assert any(item.value == 82_900_000 for item in evidence)
    assert any(item.value == 0.922 and item.unit == "percent" for item in evidence)
    assert all(item.source_sign in {-1, 1} for item in evidence)
    assert all(item.authority_rank == 1 for item in evidence)


def test_readable_event_statement_removes_filing_list_and_footnote_artifacts() -> None:
    assert _event_display_statement(
        "· The company returned $1.04 billion to shareholders. (a)"
    ) == "The company returned $1.04 billion to shareholders."
    assert _event_display_statement("●Operating EBITDA margin was 30.4%") == (
        "Operating EBITDA margin was 30.4%"
    )


def test_operating_kpi_numbers_are_owned_by_the_nearest_semantic_label() -> None:
    payload = _cost_payload()
    metric_values = {
        item["metric_name"]: item["value"]
        for event in payload["events"]
        for item in event["numeric_evidence"]
    }

    assert any("paid_members" in key and value == 82_900_000 for key, value in metric_values.items())
    assert any("cardholders" in key and value == 148_500_000 for key, value in metric_values.items())
    assert any("comparable_sales" in key and value == 0.057 for key, value in metric_values.items())
    assert any("traffic_frequency" in key and value == 0.049 for key, value in metric_values.items())
    assert any("average_ticket" in key and value == 0.008 for key, value in metric_values.items())


def test_operating_kpi_extractor_does_not_mislabel_a_year_as_a_kpi_value() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html_documents=["<p>In fiscal 2026, paid members reached 82.9 million.</p>"],
        retrieved_at="2026-08-02T12:00:00Z",
    )
    event = next(event for event in payload["events"] if "PAID_MEMBERS" in event["source_id"])
    assert [item["value"] for item in event["numeric_evidence"]] == [82_900_000]


def test_remaining_repurchase_authorization_is_not_reported_as_period_repurchases() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-07-29",
        primary_document="test.htm",
        html_documents=[
            """
            <p>As of June 30, 2026, the Company has remaining authorization for
            $2.0 billion of future share repurchases.</p>
            <p>The Company returned $1.04 billion to shareholders in the second
            quarter, consisting of $659 million in share repurchases and $379
            million in cash dividends.</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )
    facts = [
        item
        for event in payload["events"]
        for item in event["numeric_evidence"]
    ]
    authorization = next(
        item
        for item in facts
        if item["value"] == 2_000_000_000
    )
    repurchases = next(item for item in facts if item["value"] == 659_000_000)

    assert "share_repurchase_authorization_remaining" in authorization["metric_name"]
    assert authorization["period_kind"] == "instant"
    assert authorization["period_end"] == "2026-06-30"
    assert "share_repurchases" in repurchases["metric_name"]
    assert repurchases["period_kind"] == "duration"


def test_repeated_kpi_statements_have_distinct_fact_ledger_metric_ids() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html_documents=[
            """
            <p>Collection and disposal yield contributed $254 million this quarter.</p>
            <p>Collection and disposal yield contributed $102 million last quarter.</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )
    metric_ids = [
        item["metric_name"]
        for event in payload["events"]
        if "COLLECTION_DISPOSAL_YIELD" in event["source_id"]
        for item in event["numeric_evidence"]
    ]

    assert len(metric_ids) == 2
    assert len(metric_ids) == len(set(metric_ids))


def test_multiple_values_inside_one_kpi_row_receive_lossless_unique_metric_ids() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html_documents=[
            """
            <p>(in millions, except per share amounts)</p>
            <p>Three Months Ended June 30, 2026</p>
            <p>Income from Pre-tax Tax Net Diluted Per</p>
            <p>Operations Income Expense Income(a) Share Amount</p>
            <p>Stericycle acquisition and integration costs 24 24 6 18</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )
    event = next(
        event for event in payload["events"]
        if "INTEGRATION_EFFECTS" in event["source_id"]
    )
    metric_ids = [item["metric_name"] for item in event["numeric_evidence"]]

    assert len(metric_ids) == 4
    assert len(metric_ids) == len(set(metric_ids))
    assert [item["value"] for item in event["numeric_evidence"]] == [
        24_000_000,
        24_000_000,
        6_000_000,
        18_000_000,
    ]
    assert [item["column_metric"] for item in event["numeric_evidence"]] == [
        "income_from_operations",
        "pretax_income",
        "tax_expense",
        "net_income",
    ]
    assert all(item["unit"] == "currency" for item in event["numeric_evidence"])
    assert all("_event_" not in item["metric_name"] for item in event["numeric_evidence"])


def test_segment_table_preserves_dash_columns_and_exact_source_document() -> None:
    html = """
    <p>(in millions)</p>
    <p>Three Months Ended June 30, 2026</p>
    <p>Collection Processing Renewable Healthcare Corporate Total</p>
    <p>and Disposal(a)(b) and Sales(a) Energy(b) Solutions and Other WM</p>
    <p>Stericycle acquisition and integration costs — — — 14 10 24</p>
    """
    payload = build_sec_operating_kpi_payload(
        ticker="WM",
        cik="823768",
        accession_number="0001104659-26-087575",
        filing_date="2026-07-29",
        primary_document="tm2621414d1_ex99-1.htm",
        source_documents=[
            {
                "accession_number": "0001104659-26-087575",
                "filing_date": "2026-07-29",
                "primary_document": "tm2621414d1_ex99-1.htm",
                "html": html,
                "report_date": "2026-06-30",
                "report_period_months": 3,
                "document_role": "earnings_release_exhibit",
            }
        ],
        retrieved_at="2026-08-02T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )
    event = payload["events"][0]
    records = event["numeric_evidence"]

    assert event["source_accession_number"] == "0001104659-26-087575"
    assert event["source_document"] == "tm2621414d1_ex99-1.htm"
    assert event["source_document_role"] == "earnings_release_exhibit"
    assert event["source_snapshot_path"].endswith(
        "000110465926087575/tm2621414d1_ex99-1.htm"
    )
    assert len(records) == 6
    assert {item["column_metric"] for item in records} == {
        "collection_and_disposal",
        "recycling_processing_and_sales",
        "renewable_energy",
        "healthcare_solutions",
        "corporate_and_other",
        "total_wm",
    }
    assert {
        item["column_metric"]
        for item in records
        if item["source_cell_status"] == "not_applicable_dash"
    } == {
        "collection_and_disposal",
        "recycling_processing_and_sales",
        "renewable_energy",
    }


def test_all_visible_hard_numbers_in_emitted_statement_are_bound() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html_documents=[
            """
            <p>Income from operations was $1,253 million, or 18.7% of revenue,
            compared with $1,151 million, or 17.9%; the $102 million increase
            was driven by collection and disposal yield.</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )
    event = next(
        event
        for event in payload["events"]
        if "COLLECTION_DISPOSAL_YIELD" in event["source_id"]
    )

    assert [item["value"] for item in event["numeric_evidence"]] == [
        1_253_000_000,
        0.187,
        1_151_000_000,
        0.179,
        102_000_000,
    ]


def test_current_prior_and_change_tuple_gets_semantic_period_contracts() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-07-29",
        report_date="2026-06-30",
        report_period_months=3,
        primary_document="test.htm",
        html_documents=[
            "<p>Revenues of $6,684 million, compared to $6,430 million in the "
            "prior year period, an increase of $254 million, or 4.0%, driven by "
            "higher collection and disposal yield.</p>"
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )
    records = payload["events"][0]["numeric_evidence"]

    assert [item["metric_role"] for item in records] == [
        "revenue_current_period_value",
        "revenue_prior_year_value",
        "revenue_yoy_change_amount",
        "revenue_yoy_change_percent",
    ]
    assert records[0]["period_start"] == "2026-04-01"
    assert records[0]["period_end"] == "2026-06-30"
    assert records[1]["period_start"] == "2025-04-01"
    assert records[1]["period_end"] == "2025-06-30"
    assert records[2]["current_period_end"] == "2026-06-30"
    assert records[2]["comparison_period_end"] == "2025-06-30"
    assert records[2]["value"] == 254_000_000
    assert records[2]["source_sign"] == 1


def test_declining_percentages_are_bound_with_the_reported_direction() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html_documents=[
            "<p>Collection volume declined 1.8%, landfill volume grew 1.7%, "
            "and collection volume declined 0.4%.</p>"
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )
    event = next(event for event in payload["events"] if "VOLUME" in event["source_id"])

    assert [item["value"] for item in event["numeric_evidence"]] == pytest.approx(
        [-0.018, 0.017, -0.004]
    )


def test_declining_amounts_and_growth_rates_keep_direction_and_comparison_periods() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="WM",
        cik="823768",
        accession_number="0001104659-26-088016",
        filing_date="2026-07-29",
        primary_document="wm-20260630x10q.htm",
        html_documents=[
            """
            <p>Revenues from volume decreased $22 million, or 0.3%, and
            $10 million, or 0.1%, for the three and six months ended June 30,
            2026, respectively.</p>
            <p>Operating EBITDA increased 5.5% and 9.1% for the three and six
            months ended June 30, 2026, respectively.</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )
    records = [
        item for event in payload["events"] for item in event["numeric_evidence"]
    ]
    amount_changes = [
        item for item in records if "volume_revenue" in item["metric_name"] and item["unit"] == "currency"
    ]
    assert [item["value"] for item in amount_changes] == [-22_000_000, -10_000_000]
    growth = [
        item for item in records if "ebitda" in item["metric_name"] and item["unit"] == "percent"
    ]
    assert [item["period_kind"] for item in growth] == ["comparison", "comparison"]
    assert all(item["presentation_basis"] == "period_over_period_comparison" for item in growth)


def test_growth_quote_without_explicit_duration_uses_report_period_comparison() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="WM",
        cik="823768",
        accession_number="0001104659-26-087575",
        filing_date="2026-07-29",
        primary_document="ex99-1.htm",
        html_documents=[
            "<p>Adjusted operating EBITDA grew 5.5%, or 9.1% when removing "
            "contributions from wildfire cleanup activities in the prior year.</p>"
        ],
        retrieved_at="2026-08-02T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )
    records = payload["events"][0]["numeric_evidence"]
    assert [item["period_kind"] for item in records] == ["comparison", "comparison"]
    assert all(item["current_period_end"] == "2026-06-30" for item in records)
    assert all(item["comparison_period_end"] == "2025-06-30" for item in records)


def test_capital_allocation_is_extracted_as_source_bound_operating_kpi() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html_documents=[
            """
            <p>Cash dividends declared of $0.945 per common share.</p>
            <p>Cash dividends declared of $0.825 per common share.</p>
            <p>Cash dividends declared of $1.89 per common share.</p>
            <p>The company returned $1.04 billion to shareholders, consisting of
            $659 million in share repurchases and $379 million in cash dividends.</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )
    event = next(
        event
        for event in payload["events"]
        if "CAPITAL_ALLOCATION" in event["source_id"]
        and "returned $1.04 billion" in event["summary"]
    )

    assert [item["value"] for item in event["numeric_evidence"]] == [
        1_040_000_000,
        659_000_000,
        379_000_000,
    ]
    assert next(
        item
        for item in payload["kpi_dispositions"]
        if item["kpi_id"] == "capital_allocation"
    )["status"] == "found"


def test_currency_ranges_inherit_scale_and_table_headers() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html_documents=[
            """
            <p>(in millions, except per share amounts)</p>
            <p>As Reported As Adjusted(a) As Reported As Adjusted(a)</p>
            <p>Operating EBITDA $2,030 $2,067 $1,895 $1,959</p>
            <p>Adjusted EBITDA guidance is between $8.15 and $8.25 billion and
            free cash flow guidance is between $3.75 and $3.85 billion.</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )
    records = [
        item
        for event in payload["events"]
        for item in event["numeric_evidence"]
    ]
    table = next(
        event["numeric_evidence"]
        for event in payload["events"]
        if event["summary"].startswith("Operating EBITDA $2,030")
    )

    assert [item["value"] for item in table] == [
        2_030_000_000,
        2_067_000_000,
        1_895_000_000,
        1_959_000_000,
    ]
    assert [item["column_label"] for item in table] == [
        "Q2 2026 as reported",
        "Q2 2026 as adjusted",
        "Q2 2025 as reported",
        "Q2 2025 as adjusted",
    ]
    assert all(item["currency"] == "USD" for item in table)
    assert any(item["raw_value"] == 8.15 and item["value"] == 8_150_000_000 for item in records)
    assert any(item["raw_value"] == 3.75 and item["value"] == 3_750_000_000 for item in records)


def test_actual_free_cash_flow_table_is_captured_with_quarter_and_ytd_periods() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="WM",
        cik="823768",
        accession_number="0001104659-26-087575",
        filing_date="2026-07-29",
        primary_document="ex99-1.htm",
        html_documents=[
            """
            <p>(in millions)</p>
            <p>Three Months Ended June 30, Six Months Ended June 30</p>
            <p>2026 2025 2026 2025</p>
            <table><tr><td>Free cash flow</td><td>$</td><td>1,104</td>
            <td>$</td><td>818</td><td>$</td><td>2,024</td><td>$</td><td>1,293</td></tr></table>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )
    event = next(
        event for event in payload["events"]
        if event["summary"].startswith("Free cash flow")
    )
    assert [item["value"] for item in event["numeric_evidence"]] == [
        1_104_000_000,
        818_000_000,
        2_024_000_000,
        1_293_000_000,
    ]
    ytd = next(item for item in event["numeric_evidence"] if item["value"] == 2_024_000_000)
    assert ytd["period_start"] == "2026-01-01"
    assert ytd["period_end"] == "2026-06-30"


def test_actual_free_cash_flow_inherits_scale_across_split_sec_table_headers() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="WM",
        cik="823768",
        accession_number="0001104659-26-087575",
        filing_date="2026-07-29",
        primary_document="ex99-1.htm",
        html_documents=[
            """
            <p>(in millions)</p>
            <p>Three Months Ended</p><p>June 30</p>
            <p>Six Months Ended</p><p>June 30</p>
            <p>2026 2025 2026 2025</p><p>&nbsp;</p><p>&nbsp;</p><p>&nbsp;</p><p>&nbsp;</p>
            <p>Free cash flow $1,104 $818 $2,024 $1,293</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )
    event = next(
        event for event in payload["events"]
        if event["summary"].startswith("Free cash flow")
    )

    assert [item["value"] for item in event["numeric_evidence"]] == [
        1_104_000_000,
        818_000_000,
        2_024_000_000,
        1_293_000_000,
    ]


def test_adjusted_fcf_variant_is_semantically_distinct_from_plain_issuer_fcf() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="WM",
        cik="823768",
        accession_number="0001104659-26-087575",
        filing_date="2026-07-29",
        primary_document="ex99-1.htm",
        html_documents=[
            """
            <p>(in millions)</p>
            <p>Three Months Ended June 30, Six Months Ended June 30</p>
            <p>2026 2025 2026 2025</p>
            <p>Free cash flow without sustainability growth investments 1,179 978 2,160 1,581</p>
            <p>Free cash flow $1,104 $818 $2,024 $1,293</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )
    metrics = [
        item["metric_name"]
        for event in payload["events"]
        for item in event["numeric_evidence"]
    ]

    assert any("free_cash_flow_ex_sustainability_growth_actual" in metric for metric in metrics)
    assert any(
        "free_cash_flow_actual" in metric
        and "ex_sustainability_growth" not in metric
        for metric in metrics
    )
    adjusted = [
        item
        for event in payload["events"]
        for item in event["numeric_evidence"]
        if "free_cash_flow_ex_sustainability_growth_actual" in item["metric_name"]
    ]
    assert len(adjusted) == 4
    assert all(item["unit"] == "currency" for item in adjusted)
    assert all(item["currency"] == "USD" for item in adjusted)


def test_free_cash_flow_guidance_rows_are_not_promoted_as_actuals() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="WM",
        cik="823768",
        accession_number="0001104659-26-087575",
        filing_date="2026-07-29",
        primary_document="ex99-1.htm",
        html_documents=[
            """
            <p>(in millions)</p>
            <p>Free cash flow without sustainability growth investments $4,000 $4,100</p>
            <p>Free cash flow $3,750 $3,850</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )

    assert not any(
        "FREE_CASH_FLOW_ACTUAL" in event["source_id"]
        for event in payload["events"]
    )


def test_per_share_values_do_not_inherit_million_scale() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html_documents=[
            """
            <p>(in millions, except per share amounts)</p>
            <p>Cash Dividends — We paid cash dividends of $764 million and
            $669 million during the six months ended June 30, 2026 and 2025,
            respectively. The quarterly per share dividend increased from
            $0.825 in 2025 to $0.945 in 2026.</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )
    values = [
        item
        for event in payload["events"]
        for item in event["numeric_evidence"]
    ]
    per_share = [item for item in values if item["raw_value"] in {0.825, 0.945}]

    assert [item["value"] for item in per_share] == [0.825, 0.945]
    assert all(item["source_scale"] == "base" for item in per_share)
    assert all(item["unit"] == "currency_per_share" for item in per_share)
    assert any(item["raw_value"] == 764 and item["value"] == 764_000_000 for item in values)


def test_numeric_operating_kpi_event_is_not_dropped_from_claims() -> None:
    payload = _cost_payload()
    event_payload = next(
        event for event in payload["events"] if "paid_members" in event["source_id"].lower()
    )
    evidence = news_evidence_items("TEST", [event_payload])
    data = DataPacket(
        ticker="TEST",
        as_of_date="2026-08-02",
        price_basis=PriceBasis(close=100, date="2026-08-01", source="TEST_PRICE"),
        source_registry_id="TEST_sources",
        news_coverage=NewsCoverage(
            status="complete",
            material_events=[MaterialNewsEvent(**event_payload)],
        ),
    )
    metrics = MetricsPacket(
        ticker="TEST",
        as_of_date="2026-08-02",
        technical=TechnicalMetrics(indicator_date="2026-08-01", close=100),
        fundamentals=FundamentalMetrics(
            fiscal_period="TTM",
            revenue_ttm=1_000_000_000,
            operating_income_ttm=100_000_000,
            free_cash_flow_ttm=80_000_000,
        ),
        valuation=ValuationMetrics(),
    )
    validation = ValidationReport(
        ticker="TEST",
        as_of_date="2026-08-02",
        has_blocking_errors=False,
        issues=[],
    )
    decision = build_decision_packet(metrics, validation)
    claims = generate_research_claims(
        data_packet=data,
        metrics_packet=metrics,
        evidence_ledger=EvidenceLedger(
            ticker="TEST", as_of_date="2026-08-02", evidence_items=evidence
        ),
        decision_packet=decision,
        validation_report=validation,
    )

    operating_claim = next(
        claim for claim in claims if "82.9 million" in claim.claim_text
    )
    assert operating_claim.metric_refs
    assert operating_claim.evidence_ids


def test_guidance_bearing_operating_event_is_also_a_catalyst() -> None:
    event = MaterialNewsEvent(
        date="2026-08-01",
        headline="Issuer reaffirmed full-year outlook",
        event_type="operating_kpi",
        source_id="TEST_GUIDANCE",
        source_type="sec_filing",
        summary="Free cash flow guidance remains $3.75 billion to $3.85 billion.",
        numeric_evidence=[
            {
                "metric_name": "operating_kpi_free_cash_flow_guidance_01_01",
                "value": 3_750_000_000,
                "raw_value": 3.75,
                "unit": "currency",
            }
        ],
    )

    assert _is_operating_catalyst_event(event) is True
    assert _event_catalyst_summary(event.summary) == (
        "Operating catalyst under review: Free cash flow guidance remains "
        "$3.75 billion to $3.85 billion."
    )
