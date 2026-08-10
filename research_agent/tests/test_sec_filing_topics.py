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


def test_filing_topic_scanner_prioritizes_specific_current_legal_disclosures() -> None:
    payload = build_sec_filing_topic_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000003",
        filing_date="2026-07-29",
        primary_document="test.htm",
        html="""
        <p>In preparing our financial statements, difficult estimates include
        environmental remediation liabilities.</p>
        <p>The EPA issued a Unilateral Administrative Order for the San Jacinto
        cleanup in April 2026. The recorded liability was approximately
        $100 million and ultimate liability could be materially different.</p>
        <p>On April 26, 2026, the state environmental department issued an order
        alleging environmental violations. The order seeks certain remedial actions
        and an administrative penalty. Our appeal of this order is pending.</p>
        <p>In May 2026 the subsidiary entered a one-year deferred prosecution
        agreement and remains subject to compliance and reporting obligations.</p>
        <p>As of June 2026, the company had been notified that 75 locations were
        listed as Superfund sites and 14 sites were owned by the company.</p>
        <p>The majority of proceedings involving NPL sites that we do not own are
        based on transport allegations. CERCLA generally provides for liability.
        Proceedings arising under Superfund typically involve numerous generators
        and seek to allocate remediation costs that could be substantial.</p>
        """,
        retrieved_at="2026-08-02T12:00:00Z",
    )

    events = [
        item for item in payload["events"]
        if item["event_type"] == "filing_legal_contingencies"
    ]
    summaries = "\n".join(event["summary"] for event in events)
    assert len(events) == 3
    assert "San Jacinto" in summaries
    assert "deferred prosecution" in summaries
    assert "appeal of this order is pending" in summaries
    assert "75 locations" not in summaries
    assert "In preparing our financial statements" not in summaries
    san_jacinto = next(event for event in events if "San Jacinto" in event["summary"])
    assert san_jacinto["numeric_evidence"][0]["value"] == 100_000_000
    assert len({event["source_id"] for event in events}) == 3
