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


def test_separate_legal_excerpts_cannot_reuse_one_fact_metric_name() -> None:
    payload = build_sec_filing_topic_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000004",
        filing_date="2026-07-29",
        primary_document="test.htm",
        html="""
        <p>The first lawsuit seeks damages of $495 million and remains pending
        before the district court.</p>
        <p>A separate environmental proceeding seeks remediation of $120 million
        and remains subject to an administrative appeal.</p>
        """,
        retrieved_at="2026-08-02T12:00:00Z",
    )

    legal_metrics = [
        metric
        for event in payload["events"]
        if event["event_type"] == "filing_legal_contingencies"
        for metric in event["numeric_evidence"]
    ]
    assert len(legal_metrics) == 2
    assert all(metric["mapping_status"] == "unresolved" for metric in legal_metrics)
    assert all("_event_" not in metric["metric_name"] for metric in legal_metrics)


def test_legal_numbers_map_verdict_loss_range_and_recorded_accrual() -> None:
    payload = build_sec_filing_topic_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000005",
        filing_date="2026-07-29",
        primary_document="test.htm",
        html="""
        <p>The lawsuit produced a plaintiff verdict awarding $495 million in
        damages, and the matter remains on appeal.</p>
        <p>For these legal proceedings, the company estimates the range of possible loss to be from
        approximately $120 million to $530 million. The recorded accrual
        balance was approximately $510 million.</p>
        """,
        retrieved_at="2026-08-02T12:00:00Z",
    )

    metrics = {
        metric["metric_name"]: metric
        for event in payload["events"]
        if event["event_type"] == "filing_legal_contingencies"
        for metric in event["numeric_evidence"]
    }
    assert metrics["filing_legal_contingencies_verdict_damages_usd"]["value"] == 495_000_000
    assert metrics["filing_legal_contingencies_possible_loss_range_low_usd"]["value"] == 120_000_000
    assert metrics["filing_legal_contingencies_possible_loss_range_high_usd"]["value"] == 530_000_000
    assert metrics["filing_legal_contingencies_recorded_accrual_usd"]["value"] == 510_000_000
    assert all(metric["mapping_status"] == "mapped" for metric in metrics.values())


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
    assert reserve["numeric_evidence"][0]["period_kind"] == "instant"
    assert reserve["numeric_evidence"][0]["presentation_basis"] == "point_in_time"
    assert reserve["numeric_evidence"][0]["period_end"] == "2026-06-30"


def test_document_million_scale_applies_to_unscaled_debt_values() -> None:
    payload = build_sec_filing_topic_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000006",
        filing_date="2026-06-03",
        primary_document="test.htm",
        html="""
        <p>(amounts in millions)</p>
        <p>In March 2026, the subsidiary repaid $69 of its senior debt.
        The fair value of long-term debt was approximately $5,259 and $5,370.</p>
        """,
        retrieved_at="2026-08-13T12:00:00Z",
    )

    financing = next(
        event for event in payload["events"]
        if event["event_type"] == "filing_financing"
    )
    assert [item["value"] for item in financing["numeric_evidence"]] == [
        69_000_000,
        5_259_000_000,
        5_370_000_000,
    ]


def test_current_legal_class_actions_are_not_displaced_by_heading_or_fragment() -> None:
    payload = build_sec_filing_topic_payload(
        ticker="TEST",
        cik="123456",
        accession_number="0000123456-26-000007",
        filing_date="2026-06-03",
        primary_document="test.htm",
        html="""
        <p>Legal Proceedings</p>
        <p>Corp., No. C23-02416, remains pending before the court.</p>
        <p>In October and November 2025, two class actions were filed alleging
        consumer-protection violations involving tequila products. The Company
        filed a motion to dismiss in April 2026.</p>
        <p>In March 2026, four class actions were filed seeking refunds of IEEPA
        tariffs passed on through higher prices. The Company filed motions to dismiss.</p>
        """,
        retrieved_at="2026-08-13T12:00:00Z",
    )

    summaries = "\n".join(
        event["summary"]
        for event in payload["events"]
        if event["event_type"] == "filing_legal_contingencies"
    )
    assert "tequila" in summaries
    assert "IEEPA" in summaries
    assert "Legal Proceedings" not in summaries
    assert "Corp., No." not in summaries


def test_transaction_topic_preserves_ppa_and_pro_forma_rows() -> None:
    payload = build_sec_filing_topic_payload(
        ticker="TEST",
        cik="1800",
        accession_number="0001628280-26-050134",
        filing_date="2026-07-28",
        primary_document="test.htm",
        html="""
        <p>(dollars in millions)</p>
        <p>On March 23, 2026, the company completed the business combination.</p>
        <p>The following table summarizes the preliminary allocation of fair value.</p>
        <tr><td>Goodwill</td><td>17,153</td></tr>
        <tr><td>Acquired intangible assets</td><td>12,800</td></tr>
        <p>Pro forma consolidated net sales for the six months ended June 30, 2026
        were $25,900.</p>
        """,
        retrieved_at="2026-08-13T12:00:00Z",
    )

    metrics = {
        item["metric_name"]: item
        for event in payload["events"]
        if event["event_type"] == "filing_transactions"
        for item in event["numeric_evidence"]
        if item["mapping_status"] == "mapped"
    }
    assert any("acquisition_goodwill" in name for name in metrics)
    assert any("acquisition_intangible_assets" in name for name in metrics)
    assert any("acquisition_pro_forma_net_sales" in name for name in metrics)
    assert any(item["value"] == 17_153_000_000 for item in metrics.values())
