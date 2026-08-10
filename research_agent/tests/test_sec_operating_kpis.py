from research_agent.content.claim_generator import generate_research_claims
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
    assert all(item.authority_rank == 1 for item in evidence)


def test_operating_kpi_numbers_are_owned_by_the_nearest_semantic_label() -> None:
    payload = _cost_payload()
    events = {
        event["source_id"].split("_KPI_", 1)[1].rsplit("_", 1)[0].lower(): event
        for event in payload["events"]
    }

    assert [item["value"] for item in events["paid_members"]["numeric_evidence"]] == [
        82_900_000
    ]
    assert [item["value"] for item in events["cardholders"]["numeric_evidence"]] == [
        148_500_000
    ]
    assert [item["value"] for item in events["comparable_sales"]["numeric_evidence"]] == [
        0.057
    ]
    assert [item["value"] for item in events["traffic_frequency"]["numeric_evidence"]] == [
        0.049
    ]
    assert [item["value"] for item in events["average_ticket"]["numeric_evidence"]] == [
        0.008
    ]


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
