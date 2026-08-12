import pytest

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
        <p>In May 2026 the subsidiary entered settlement agreements, including
        a one-year deferred prosecution agreement, made the agreed penalty and
        settlement payments, and remains subject to continuing compliance,
        reporting and cooperation obligations. We do not currently believe this
        matter will have a material adverse effect on the company.</p>
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
    assert san_jacinto["legal_context"]["reserve_or_obligation_present"] is True
    assert san_jacinto["legal_context"]["uncertainty_present"] is True
    stericycle = next(event for event in events if "deferred prosecution" in event["summary"])
    assert stericycle["legal_context"]["latest_status_present"] is True
    assert stericycle["legal_context"]["continuing_obligations_present"] is True
    assert stericycle["legal_context"]["management_assessment_present"] is True
    assert len({event["source_id"] for event in events}) == 3


def test_topic_numbers_keep_semantic_cardinality_and_distinct_debt_coupons() -> None:
    payload = build_sec_filing_topic_payload(
        ticker="WM",
        cik="823768",
        accession_number="0001104659-26-088016",
        filing_date="2026-07-29",
        primary_document="wm-20260630x10q.htm",
        html="""
        <p>During the six months ended June 30, 2026, we completed solid waste
        acquisitions for total consideration of $235 million, which included
        issuance of shares valued at $144 million, $85 million in net cash paid
        and $6 million of other consideration, specifically purchase price
        holdbacks. In addition, we paid $13 million of holdbacks related to
        prior year acquisitions.</p>
        <p>We issued C$700 million of 3.944% senior notes. The net proceeds were
        C$696 million and were used to redeem previously outstanding C$500
        million 2.60% senior notes.</p>
        """,
        retrieved_at="2026-08-02T12:00:00Z",
    )
    transaction = next(
        event for event in payload["events"]
        if event["event_type"] == "filing_transactions"
    )
    financing = next(
        event for event in payload["events"]
        if event["event_type"] == "filing_financing"
    )
    transaction_metrics = {
        item["metric_name"]: item["value"]
        for item in transaction["numeric_evidence"]
    }
    assert len(transaction_metrics) == 5
    assert transaction_metrics["filing_transactions_acquisition_total_consideration_usd"] == 235_000_000
    assert transaction_metrics["filing_transactions_acquisition_stock_consideration_usd"] == 144_000_000
    assert transaction_metrics["filing_transactions_acquisition_net_cash_paid_usd"] == 85_000_000
    assert transaction_metrics["filing_transactions_acquisition_other_consideration_usd"] == 6_000_000
    assert transaction_metrics["filing_transactions_acquisition_prior_period_holdback_usd"] == 13_000_000
    financing_metrics = {
        item["metric_name"]: item["value"]
        for item in financing["numeric_evidence"]
    }
    assert financing_metrics["filing_financing_issued_interest_rate"] == 0.03944
    assert financing_metrics["filing_financing_refinanced_interest_rate"] == pytest.approx(0.026)


def test_legal_topic_preserves_preceding_issuer_assessment_and_effective_dates() -> None:
    payload = build_sec_filing_topic_payload(
        ticker="WM",
        cik="823768",
        accession_number="0001104659-26-088016",
        filing_date="2026-07-29",
        primary_document="wm-20260630x10q.htm",
        html="""
        <p>We do not currently believe that the eventual outcome of this matter
        will have a material adverse effect on the Company.</p>
        <p>On April 26, 2026, the environmental department issued an order
        alleging environmental violations. The order seeks remedial actions
        and an administrative penalty. Our appeal of this order is pending.</p>
        <p>The recorded liability as of June 30, 2026, and December 31, 2025,
        was approximately $100 million. Ultimate liability could be materially
        different from current estimates.</p>
        """,
        retrieved_at="2026-08-02T12:00:00Z",
    )
    legal = [
        event for event in payload["events"]
        if event["event_type"] == "filing_legal_contingencies"
    ]
    order = next(event for event in legal if "issued an order" in event["summary"])
    assert order["summary"].startswith("We do not currently believe")
    assert order["legal_context"]["management_assessment_present"] is True
    reserve = next(event for event in legal if "recorded liability" in event["summary"])
    assert reserve["numeric_evidence"][0]["effective_asof_dates"] == [
        "2026-06-30",
        "2025-12-31",
    ]
