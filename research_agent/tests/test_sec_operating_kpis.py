import pytest

from research_agent.content.claim_generator import generate_research_claims
from research_agent.content.claim_generator import (
    _event_display_statement,
    _event_catalyst_summary,
    _event_metric_is_visible,
    _is_operating_catalyst_event,
)
from research_agent.decision.rating_engine import build_decision_packet
from research_agent.evidence.evidence_ledger import EvidenceLedger
from research_agent.research_core.ingestion.news_loader import news_evidence_items
from research_agent.research_core.models.data_packet import (
    DataPacket,
    MaterialNewsEvent,
    NewsCoverage,
    OperatingKpiEvidence,
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
    _numeric_direction_contract,
    _numeric_evidence,
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


def test_event_metric_visibility_recognizes_source_thousands_separators() -> None:
    metric = OperatingKpiEvidence(
        metric_name="filing_financing_debt_principal_usd",
        value=5259.0,
        raw_value=5259.0,
        unit="USD",
    )

    assert _event_metric_is_visible(metric, "Debt fair value was $5,259.")


def test_page_break_parenthetical_tail_is_not_promoted_as_operating_context() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html_documents=[
            "<p>installation) and other businesses (e-commerce and travel). "
            "Comparable sales increased 2%.</p>"
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )

    assert payload["events"] == []


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


def test_transaction_financing_amounts_have_distinct_semantic_owners() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="1800",
        accession_number="0001628280-26-050134",
        filing_date="2026-07-28",
        primary_document="test.htm",
        html_documents=[
            """
            <p>Abbott completed the acquisition of Exact Sciences for approximately
            $20.6 billion. Abbott issued $20.0 billion of debt to finance the
            acquisition. Under the acquisition agreement, Abbott paid $105 per
            common share in cash. As part of the acquisition, Abbott assumed
            approximately $2.8 billion of Exact Sciences debt.</p>
            """
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )

    metrics = {
        metric["metric_name"]: metric["value"]
        for event in payload["events"]
        for metric in event["numeric_evidence"]
        if metric["mapping_status"] == "mapped"
    }
    assert metrics["operating_kpi_acquisition_total_consideration_3m_2026-06-30_amount"] == 20_600_000_000
    assert metrics["operating_kpi_acquisition_debt_issued_3m_2026-06-30_amount"] == 20_000_000_000
    assert metrics["operating_kpi_acquisition_purchase_price_per_share_3m_2026-06-30_amount"] == 105
    assert metrics["operating_kpi_acquisition_assumed_debt_3m_2026-06-30_amount"] == 2_800_000_000


def test_inline_year_dividend_table_keeps_year_and_per_share_identity() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="1800",
        accession_number="0001628280-26-050134",
        filing_date="2026-07-28",
        primary_document="test.htm",
        html_documents=[
            "<p>Cash dividends declared on common shares "
            "(per share — 2026: $0.63; 2025: $0.59)</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )

    metrics = [
        metric
        for event in payload["events"]
        for metric in event["numeric_evidence"]
    ]
    assert [metric["period_end"] for metric in metrics] == [
        "2026-06-30",
        "2025-06-30",
    ]
    assert [metric["unit"] for metric in metrics] == [
        "currency_per_share",
        "currency_per_share",
    ]
    assert [metric["value"] for metric in metrics] == [0.63, 0.59]


def test_distant_dividend_mention_does_not_own_pension_amounts() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="1800",
        accession_number="0001628280-26-010185",
        filing_date="2026-02-20",
        primary_document="test.htm",
        html_documents=[
            "<p>Abbott funded $309 million in 2025 and $349 million in 2024 to "
            "defined benefit pension plans. Abbott expects to contribute "
            "$85 million in 2026. Operating cash flow is expected to exceed "
            "capital expenditures and cash dividends.</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2025-12-31",
        report_period_months=12,
    )

    metrics = [
        metric
        for event in payload["events"]
        for metric in event["numeric_evidence"]
    ]
    assert metrics
    assert all("cash_dividends" not in metric["metric_name"] for metric in metrics)
    assert all("pension_contributions" in metric["metric_name"] for metric in metrics)
    assert all(metric["mapping_status"] == "mapped" for metric in metrics)


def test_spelled_percent_is_not_scaled_by_nearby_billions() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="1800",
        accession_number="0001628280-26-010185",
        filing_date="2026-02-20",
        primary_document="test.htm",
        html_documents=[
            "<p>Core Laboratory segment growth was driven as sales increased "
            "2.1 percent in 2025 "
            "and 5.6 percent in 2024. "
            "Sales later totaled $7.6 billion.</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2025-12-31",
        report_period_months=12,
    )

    percent_metrics = [
        metric
        for event in payload["events"]
        for metric in event["numeric_evidence"]
        if metric["dimension"] == "percent"
    ]
    assert [metric["value"] for metric in percent_metrics] == pytest.approx(
        [0.021, 0.056]
    )
    assert all(metric["source_scale"] == "percent" for metric in percent_metrics)


def test_net_sales_total_is_not_owned_by_a_later_comparable_sales_explanation() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-06-03",
        primary_document="test.htm",
        html_documents=[
            "<p>Net sales increased 12% to $69,154, driven by an increase in "
            "comparable sales and new locations.</p>"
        ],
        retrieved_at="2026-08-12T12:00:00Z",
        report_date="2026-05-10",
        report_period_months=3,
    )
    records = payload["events"][0]["numeric_evidence"]

    assert [item["metric_role"] for item in records] == [
        "revenue_yoy_change_3m_2026-05-10_ratio",
        "revenue_3m_2026-05-10_amount",
    ]
    assert [item["fact_type"] for item in records] == [
        "year_over_year_change",
        "period_total",
    ]
    assert [item["value"] for item in records] == [0.12, 69_154.0]


def test_paired_quarter_and_year_to_date_prose_keeps_metric_and_period_identity() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-06-03",
        primary_document="test.htm",
        html_documents=[
            "<p>Net sales increased $7,189 or 12%, and $17,894 or 10% during "
            "the third quarter and first thirty-six weeks of 2026. The "
            "improvement was primarily attributable to an increase in comparable "
            "sales of $6,055 or 10% and $14,553 or 8% during the third quarter "
            "and thirty-six weeks of 2026. Comparable sales were positively "
            "impacted by increases of approximately 7% and 5% in average ticket "
            "and 2% and 3% in shopping frequency in the third quarter and first "
            "thirty-six weeks of 2026.</p>"
        ],
        retrieved_at="2026-08-12T12:00:00Z",
        report_date="2026-05-10",
        report_period_months=3,
    )
    records = payload["events"][0]["numeric_evidence"]
    by_value = {(item["metric_role"], item["value"]): item for item in records}

    expected = {
        ("revenue_yoy_change_12w_2026-05-10_amount", 7_189.0): "2026-02-16",
        ("revenue_yoy_change_12w_2026-05-10_ratio", 0.12): "2026-02-16",
        ("revenue_yoy_change_36w_2026-05-10_amount", 17_894.0): "2025-09-01",
        ("revenue_yoy_change_36w_2026-05-10_ratio", 0.10): "2025-09-01",
        ("comparable_sales_yoy_change_12w_2026-05-10_amount", 6_055.0): "2026-02-16",
        ("comparable_sales_yoy_change_12w_2026-05-10_ratio", 0.10): "2026-02-16",
        ("comparable_sales_yoy_change_36w_2026-05-10_amount", 14_553.0): "2025-09-01",
        ("comparable_sales_yoy_change_36w_2026-05-10_ratio", 0.08): "2025-09-01",
        ("average_ticket_yoy_change_12w_2026-05-10_ratio", 0.07): "2026-02-16",
        ("average_ticket_yoy_change_36w_2026-05-10_ratio", 0.05): "2025-09-01",
        ("traffic_frequency_yoy_change_12w_2026-05-10_ratio", 0.02): "2026-02-16",
        ("traffic_frequency_yoy_change_36w_2026-05-10_ratio", 0.03): "2025-09-01",
    }
    assert set(by_value) == set(expected)
    for key, period_start in expected.items():
        assert by_value[key]["period_start"] == period_start
        assert by_value[key]["mapping_status"] == "mapped"
        if key[0].startswith(("average_ticket", "traffic_frequency")):
            assert by_value[key]["direction"] == "increase"
            assert by_value[key]["impact"] == "positive"


def test_increased_operating_expense_is_directionally_adverse() -> None:
    statement = "Operating expenses increased $152 million during the six months ended June 30, 2026."
    start = statement.index("$152")
    result = _numeric_direction_contract(statement, (start, start + len("$152 million")))

    assert result == (1.0, "increase", "adverse")


def test_digitally_enabled_comparable_sales_remains_distinct_and_multi_period_value_is_unresolved() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-06-03",
        primary_document="test.htm",
        html_documents=[
            "<p>Digitally-enabled comparable sales increased 21% and 22% during "
            "the third quarter and first thirty-six weeks of 2026 and increased "
            "21% for each period excluding foreign currencies.</p>"
        ],
        retrieved_at="2026-08-12T12:00:00Z",
        report_date="2026-05-10",
        report_period_months=3,
    )
    records = payload["events"][0]["numeric_evidence"]

    assert [item["metric_role"] for item in records[:2]] == [
        "digital_sales_yoy_change_12w_2026-05-10_ratio",
        "digital_sales_yoy_change_36w_2026-05-10_ratio",
    ]
    assert [item["mapping_status"] for item in records] == [
        "mapped",
        "mapped",
        "unresolved",
    ]


def test_split_membership_table_rows_preserve_years_counts_and_scale() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2025-10-08",
        primary_document="test.htm",
        html_documents=[
            "<p>Membership at year end was as follows (in thousands):</p>"
            "<p>202520242023</p>"
            "<p>Total paid members<sup>1</sup></p>"
            "<p>81,000 76,200 71,000</p>"
            "<p>Total cardholders145,200 136,800 127,900</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2025-08-31",
        report_period_months=12,
    )
    records = [
        item
        for event in payload["events"]
        for item in event["numeric_evidence"]
    ]
    paid = [item for item in records if item.get("row_metric") == "total_paid_members"]
    cardholders = [item for item in records if item.get("row_metric") == "total_cardholders"]

    assert [item["value"] for item in paid] == [81_000_000, 76_200_000, 71_000_000]
    assert [item["value"] for item in cardholders] == [145_200_000, 136_800_000, 127_900_000]
    assert [item["period_end"] for item in paid] == [
        "2025-08-31",
        "2024-08-31",
        "2023-08-31",
    ]
    assert all(item["unit"] == "count" and item["mapping_status"] == "mapped" for item in paid + cardholders)


def test_split_fiscal_week_membership_table_keeps_current_counts_and_dates() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-06-03",
        primary_document="test.htm",
        html_documents=[
            "<p>Membership Fees</p>"
            "<p>12 Weeks Ended36 Weeks Ended</p>"
            "<p>May 10,</p><p>2026May 11,</p><p>2025May 10,</p><p>2026May 11,</p><p>2025</p>"
            "<p>Total paid members (000s)82,900 79,600 — —</p>"
            "<p>Total cardholders (000s)148,500 142,800 — —</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2026-05-10",
        report_period_months=3,
    )
    records = [
        item
        for event in payload["events"]
        for item in event["numeric_evidence"]
    ]
    paid = [item for item in records if item["metric_role"].startswith("paid_members_")]
    cardholders = [item for item in records if item["metric_role"].startswith("cardholders_")]

    assert [(item["value"], item["period_end"]) for item in paid] == [
        (82_900_000, "2026-05-10"),
        (79_600_000, "2025-05-11"),
    ]
    assert [(item["value"], item["period_end"]) for item in cardholders] == [
        (148_500_000, "2026-05-10"),
        (142_800_000, "2025-05-11"),
    ]
    assert all(item["period_kind"] == "instant" for item in paid + cardholders)


def test_current_renewal_rates_keep_distinct_geographic_roles() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-06-03",
        primary_document="test.htm",
        html_documents=[
            "<p>At the end of the third quarter of 2026, our renewal rates were "
            "92.2% in the U.S. and Canada and 89.7% worldwide.</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2026-05-10",
        report_period_months=3,
    )
    records = payload["events"][0]["numeric_evidence"]

    assert [item["metric_role"] for item in records] == [
        "renewal_rate_asof_2026-05-10_us_canada_ratio",
        "renewal_rate_asof_2026-05-10_worldwide_ratio",
    ]
    assert all(item["mapping_status"] == "mapped" for item in records)
    assert all(item["fact_type"] == "instant_value" for item in records)
    assert all(item["period_kind"] == "instant" for item in records)


def test_membership_fee_and_reward_caps_do_not_inherit_document_millions_scale() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2025-10-08",
        primary_document="test.htm",
        html_documents=[
            "<p>(amounts in millions)</p>"
            "<p>Paid members may upgrade for an additional annual fee of $65. "
            "Executive members earn a 2% reward up to a maximum reward of "
            "$1,250 per year.</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2025-08-31",
        report_period_months=12,
    )
    records = payload["events"][0]["numeric_evidence"]

    assert [(item["metric_role"].split("_12m", 1)[0], item["value"]) for item in records] == [
        ("membership_annual_fee", 65.0),
        ("membership_reward_rate", 0.02),
        ("membership_reward_cap", 1250.0),
    ]


def test_executive_member_footnote_is_not_promoted_and_years_remain_aligned() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2025-10-08",
        primary_document="test.htm",
        html_documents=[
            "<p>(in thousands)</p>"
            "<p>2025 2024 2023</p>"
            "<p>(1) Executive members represented 38,700, 35,400, and 32,300 "
            "of total paid members in 2025, 2024, and 2023.</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2025-08-31",
        report_period_months=12,
    )

    records = [
        item
        for event in payload["events"]
        for item in event["numeric_evidence"]
    ]
    assert [item["value"] for item in records] == [38_700_000, 35_400_000, 32_300_000]
    assert all("executive_members" in item["metric_role"] for item in records)
    assert all("paid_members" not in item["metric_role"] for item in records)
    assert all(item["period_kind"] == "instant" for item in records)
    assert [item["period_end"] for item in records] == [
        "2025-08-31",
        "2024-08-31",
        "2023-08-31",
    ]
    assert [item["raw_text"] for item in records] == [
        "38,700 [FY2025]",
        "35,400 [FY2024]",
        "32,300 [FY2023]",
    ]


def test_healthcare_release_extracts_current_segment_axes_and_catalysts() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="1800",
        accession_number="0001628280-26-048377",
        filing_date="2026-07-16",
        primary_document="test.htm",
        html_documents=[
            "<p>Sales 2Q26 ($ in millions)</p>"
            "<p>Total Company Nutrition Diagnostics Established Pharmaceuticals Medical Devices</p>"
            "<p>Total reported13.0 (3.1)42.3 8.4 9.0</p>"
            "<p>Comparable sales growth4.8 (3.6)2.9 8.7 8.4</p>"
            "<p>In May, Abbott announced it secured CE Mark for Libre Duo, the world's first dual glucose-ketone biowearable sensor.</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )
    facts = [
        item
        for event in payload["events"]
        for item in event["numeric_evidence"]
    ]
    expected = {
        ("segment_reported_sales_growth", "diagnostics"): 0.423,
        ("comparable_sales_growth", "diagnostics"): 0.029,
        ("comparable_sales_growth", "established_pharmaceuticals"): 0.087,
        ("comparable_sales_growth", "medical_devices"): 0.084,
    }
    for (metric, segment), value in expected.items():
        fact = next(
            item
            for item in facts
            if metric in item["metric_name"] and item["segment"] == segment
        )
        assert fact["value"] == pytest.approx(value)
        assert fact["period_kind"] == "comparison"
    catalyst = next(
        event
        for event in payload["events"]
        if "PRODUCT_REGULATORY_CATALYST" in event["source_id"]
    )
    assert catalyst["numeric_evidence"] == []


def test_guidance_range_endpoints_keep_range_fact_type() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-07-29",
        primary_document="test.htm",
        html_documents=[
            "<p>We increased free cash flow guidance to a range of "
            "$2.9 billion to $3.1 billion for fiscal 2026.</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )
    records = [item for event in payload["events"] for item in event["numeric_evidence"]]

    assert len(records) == 2
    assert all(item["presentation_basis"] == "guidance_range" for item in records)
    assert all(item["fact_type"] == "guidance_range" for item in records)


def test_acquisition_cash_flow_row_keeps_six_month_period_and_scale() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="1800",
        accession_number="0001628280-26-050134",
        filing_date="2026-07-28",
        primary_document="test.htm",
        html_documents=[
            "<p>(dollars in millions)</p>"
            "<p>Six Months Ended June 30</p>"
            "<p>2026 2025</p>"
            "<tr><td>Acquisitions of businesses and technologies, net of cash acquired</td>"
            "<td>(19,962)</td><td>(30)</td></tr>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )

    records = payload["events"][0]["numeric_evidence"]
    assert [item["value"] for item in records] == [19_962_000_000, 30_000_000]
    assert [item["period_start"] for item in records] == ["2026-01-01", "2025-01-01"]
    assert all(item["dimension"] == "currency" for item in records)
    assert all(item["currency"] == "USD" for item in records)
    assert all("acquisition_net_cash_paid" in item["metric_name"] for item in records)


def test_transaction_amounts_use_nearest_economic_event_date() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="1800",
        accession_number="0001628280-26-050134",
        filing_date="2026-07-28",
        primary_document="test.htm",
        html_documents=[
            "<p>On March 23, 2026, Abbott completed the acquisition for "
            "approximately $20.6 billion and paid $105 per common share.</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )

    records = payload["events"][0]["numeric_evidence"]
    assert all(item["period_kind"] == "instant" for item in records)
    assert all(item["period_end"] == "2026-03-23" for item in records)
    per_share = next(item for item in records if item["value"] == 105)
    assert per_share["fact_type"] == "stock_value"


def test_material_warehouse_count_is_not_mislabeled_as_revenue() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-06-03",
        primary_document="test.htm",
        html_documents=[
            "<p>Net sales increased 12% to $69,154, driven by comparable sales and sales at "
            "23 net new warehouses opened since the prior-year quarter.</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2026-05-10",
        report_period_months=3,
    )

    warehouse = next(
        item
        for event in payload["events"]
        for item in event["numeric_evidence"]
        if "net_new_warehouses" in item["metric_name"]
    )
    assert warehouse["value"] == 23
    assert warehouse["dimension"] == "count"


def test_accounting_policy_words_do_not_create_operating_kpis() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="1800",
        accession_number="0001628280-26-050134",
        filing_date="2026-07-28",
        primary_document="test.htm",
        html_documents=[
            "<p>Transactions involving intangible assets occur with some frequency. "
            "The $24 billion goodwill balance is reviewed for impairment.</p>"
            "<p>An in-process asset of $15 million remains indefinite-lived until "
            "regulatory approval or discontinuation.</p>"
            "<p>The company operates 928 warehouses and e-commerce sites.</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )

    assert payload["events"] == []


def test_annual_revenue_change_amount_is_distinct_from_annual_revenue_total() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2025-10-08",
        primary_document="test.htm",
        html_documents=[
            "<p>(amounts in millions)</p>"
            "<p>Net sales increased 8% to $269,912, driven by comparable sales.</p>"
            "<p>Net sales increased $20,287 or 8% during 2025, driven by comparable sales.</p>"
        ],
        retrieved_at="2026-08-13T12:00:00Z",
        report_date="2025-08-31",
        report_period_months=12,
    )
    records = [item for event in payload["events"] for item in event["numeric_evidence"]]

    assert any(
        item["metric_role"] == "revenue_12m_2025-08-31_amount"
        and item["value"] == 269_912_000_000
        for item in records
    )
    assert any(
        item["metric_role"] == "revenue_yoy_change_12m_2025-08-31_amount"
        and item["value"] == 20_287_000_000
        for item in records
    )


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


def test_current_and_previous_quarter_language_uses_known_report_period() -> None:
    payload = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html_documents=[
            "<p>Collection and disposal yield contributed $254 million this quarter.</p>"
            "<p>Collection and disposal yield contributed $102 million last quarter.</p>"
        ],
        retrieved_at="2026-08-02T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )
    records = [
        item
        for event in payload["events"]
        for item in event["numeric_evidence"]
    ]
    current = next(item for item in records if item["value"] == 254_000_000)
    previous = next(item for item in records if item["value"] == 102_000_000)

    assert (current["period_start"], current["period_end"]) == (
        "2026-04-01",
        "2026-06-30",
    )
    assert (previous["period_start"], previous["period_end"]) == (
        "2026-01-01",
        "2026-03-31",
    )


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


def test_non_monetary_cell_does_not_inherit_table_currency() -> None:
    rows = _numeric_evidence(
        "Adjusted operating EBITDA margin guidance increased 20 basis points.",
        kpi_ids=["operating_ebitda"],
        event_index=0,
        context_scale="million",
        filing_date="2026-07-29",
        report_date="2026-06-30",
        report_period_months=3,
    )

    row = next(item for item in rows if item["source_scale"] == "basis_points")
    assert row["unit"] == "basis_points"
    assert row["dimension"] == "basis_points"
    assert row["display_unit"] == "basis_points"
    assert row["currency"] is None


def test_sequential_basis_point_change_uses_comparison_period() -> None:
    rows = _numeric_evidence(
        "Collection and Disposal volume declined 1.8%, primarily due to prior "
        "year wildfire cleanup. Residential volume losses have begun to slow, "
        "with losses improving sequentially by 210 basis points.",
        kpi_ids=["volume"],
        event_index=0,
        filing_date="2026-07-29",
        report_date="2026-06-30",
        report_period_months=3,
    )

    row = next(item for item in rows if item["source_scale"] == "basis_points")
    assert row["fact_type"] == "basis_point_change"
    assert row["period_kind"] == "comparison"
    assert row["current_period_start"] == "2026-04-01"
    assert row["current_period_end"] == "2026-06-30"
    assert row["comparison_period_start"] == "2026-01-01"
    assert row["comparison_period_end"] == "2026-03-31"
    assert row["signed_value"] == 210.0
    assert row["direction"] == "increase"
    assert row["impact"] == "positive"


def test_paired_change_amount_inherits_direction_across_and() -> None:
    rows = _numeric_evidence(
        "The improvement was primarily attributable to an increase in comparable "
        "sales of $6,055 or 10% and $14,553 or 8% during the third quarter and "
        "thirty-six weeks of 2026.",
        kpi_ids=["comparable_sales"],
        event_index=0,
        context_scale="million",
        filing_date="2026-06-03",
        report_date="2026-05-10",
        report_period_months=9,
    )

    row = next(item for item in rows if item["raw_value"] == 14_553.0)
    assert row["fact_type"] == "year_over_year_change"
    assert row["signed_value"] == 14_553_000_000.0
    assert row["direction"] == "increase"
    assert row["impact"] == "positive"


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
        "revenue_current_period_value_3m_2026-06-30",
        "revenue_prior_year_value_3m_2025-06-30",
        "revenue_yoy_change_amount_3m_2026-06-30",
        "revenue_yoy_change_percent_3m_2026-06-30",
    ]
    assert records[0]["period_start"] == "2026-04-01"
    assert records[0]["period_end"] == "2026-06-30"
    assert records[1]["period_start"] == "2025-04-01"
    assert records[1]["period_end"] == "2025-06-30"
    assert records[2]["current_period_end"] == "2026-06-30"
    assert records[2]["comparison_period_end"] == "2025-06-30"
    assert records[2]["value"] == 254_000_000
    assert records[2]["source_sign"] == 1


def test_same_metric_in_quarter_and_fiscal_year_gets_distinct_metric_ids() -> None:
    quarter = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-07-29",
        report_date="2026-06-30",
        report_period_months=3,
        primary_document="q2.htm",
        html_documents=[
            "<p>Revenues of $6,684 million, compared to $6,430 million in the "
            "prior year period, an increase of $254 million, or 4.0%, driven "
            "by higher collection and disposal yield.</p>"
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )
    year = build_sec_operating_kpi_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000002",
        filing_date="2026-02-09",
        report_date="2025-12-31",
        report_period_months=12,
        primary_document="fy.htm",
        html_documents=[
            "<p>Revenues of $25,204 million for 2025 compared with $22,063 "
            "million in 2024, an increase of $3,141 million, or 14.2%, driven "
            "by higher collection and disposal yield.</p>"
        ],
        retrieved_at="2026-08-02T12:00:00Z",
    )

    quarter_metric = quarter["events"][0]["numeric_evidence"][0]["metric_name"]
    year_metric = year["events"][0]["numeric_evidence"][0]["metric_name"]
    assert quarter_metric == "operating_kpi_revenue_current_period_value_3m_2026-06-30"
    assert year_metric == "operating_kpi_revenue_current_period_value_12m_2025-12-31"
    assert quarter_metric != year_metric


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


def _claims_for_operating_event(event_payload: dict):
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
    return generate_research_claims(
        data_packet=data,
        metrics_packet=metrics,
        evidence_ledger=EvidenceLedger(
            ticker="TEST", as_of_date="2026-08-02", evidence_items=evidence
        ),
        decision_packet=decision,
        validation_report=validation,
    )


def test_numeric_operating_kpi_event_is_not_dropped_from_claims() -> None:
    payload = _cost_payload()
    event_payload = next(
        event for event in payload["events"] if "paid_members" in event["source_id"].lower()
    )
    claims = _claims_for_operating_event(event_payload)

    operating_claim = next(
        claim for claim in claims if "82.9 million" in claim.claim_text
    )
    assert operating_claim.metric_refs
    assert operating_claim.evidence_ids


def test_event_with_any_unresolved_numeric_identity_is_not_promoted_to_claims() -> None:
    payload = _cost_payload()
    event_payload = next(
        event for event in payload["events"] if "paid_members" in event["source_id"].lower()
    )
    event_payload["numeric_evidence"][0]["mapping_status"] = "unresolved"

    claims = _claims_for_operating_event(event_payload)

    assert not any("82.9 million" in claim.claim_text for claim in claims)


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


def test_product_milestone_is_catalyst_but_generic_regulatory_risk_is_not() -> None:
    milestone = MaterialNewsEvent(
        date="2026-07-16",
        headline="Issuer product update",
        event_type="operating_kpi",
        source_id="TEST_PRODUCT_CATALYST",
        source_type="sec_filing",
        summary=(
            "Abbott completed its submission to the U.S. Food and Drug "
            "Administration (FDA) seeking approval for the Amulet 360 left "
            "atrial appendage device."
        ),
    )
    generic_risk = milestone.model_copy(
        update={
            "source_id": "TEST_GENERIC_REGULATORY_RISK",
            "summary": (
                "No assurance can be given that the issuer will remain in "
                "compliance after regulatory approval has been obtained."
            ),
        }
    )

    assert _is_operating_catalyst_event(milestone) is True
    assert _is_operating_catalyst_event(generic_risk) is False
    claims = _claims_for_operating_event(milestone.model_dump())
    assert any(
        claim.section == "Catalysts & Triggers"
        and "Amulet 360 left atrial appendage device" in claim.claim_text
        for claim in claims
    )
