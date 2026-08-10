from research_agent.sources.sec.sec_filing_topics import (
    build_sec_filing_topic_payload,
)


def test_filing_topic_scanner_dispositions_all_required_topics() -> None:
    payload = build_sec_filing_topic_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000001",
        filing_date="2026-08-01",
        primary_document="test-20260630.htm",
        html="""
        <p>The company completed the acquisition of Example GmbH for $250 million.</p>
        <p>We entered into a new revolving credit facility with $500 million available.</p>
        <p>Environmental remediation liabilities were $12 million at quarter end.</p>
        """,
        retrieved_at="2026-08-02T12:00:00Z",
    )

    assert payload["coverage_status"] == "complete"
    assert payload["all_topics_dispositioned"] is True
    statuses = {
        item["topic"]: item["status"] for item in payload["topic_dispositions"]
    }
    assert statuses == {
        "transactions": "found_specific_disclosure",
        "financing": "found_specific_disclosure",
        "legal_contingencies": "found_specific_disclosure",
    }
    assert len(payload["events"]) == 3


def test_filing_topic_scanner_records_no_specific_disclosure() -> None:
    payload = build_sec_filing_topic_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000002",
        filing_date="2026-08-01",
        primary_document="test.htm",
        html="<p>The company sells ordinary consumer products.</p>",
        retrieved_at="2026-08-02T12:00:00Z",
    )

    assert payload["events"] == []
    assert {
        item["status"] for item in payload["topic_dispositions"]
    } == {"reviewed_no_specific_disclosure"}
