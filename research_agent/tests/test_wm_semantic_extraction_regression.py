"""Real-source WM statements that previously produced semantic false passes."""

from research_agent.quality.semantic_contracts import audit_semantic_records
from research_agent.sources.sec.sec_operating_kpis import build_sec_operating_kpi_payload


def _wm_payload():
    return build_sec_operating_kpi_payload(
        ticker="WM",
        cik="823768",
        accession_number="0001104659-26-087575",
        filing_date="2026-07-29",
        primary_document="tm2621414d1_ex99-1.htm",
        html_documents=[
            """
            <p>(in millions)</p>
            <p>Three Months Ended Six Months Ended</p>
            <p>June 30, 2026 2025 2026 2025</p>
            <p>Total average yield $277 4.3% $441 3.5 %</p>
            <p>Cash Dividends — We paid cash dividends of $764 million and $669
            million during the six months ended June 30, 2026 and 2025
            respectively. The increase in dividend payments is primarily due
            to our quarterly per share dividend increasing from $0.825 in 2025
            to $0.945 in 2026.</p>
            <p>Collection and Disposal operating EBITDA grew by $104 million,
            or $79 million on an adjusted basis. Growth overcame a 70-basis
            point headwind to the segment from wildfire cleanup contributions
            in the prior year.</p>
            <p>Revenue is now expected to be between $26.275 and $26.475
            billion dollars, reflecting a reduction of approximately 0.6%
            compared to the prior outlook, primarily driven by lower volume
            expectations.</p>
            <p>Gross annualized revenue acquired $123 million.</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=6,
    )


def test_wm_yield_period_measure_axes_are_not_flattened_into_four_timepoints():
    payload = _wm_payload()
    event = next(event for event in payload["events"] if "Total average yield" in event["summary"])
    facts = event["numeric_evidence"]
    table = event["table_contracts"][0]

    assert table["period_axis"] == ["3M 2026", "6M 2026"]
    assert table["metric_axis"] == ["year_over_year_change_usd", "share_of_total_pct"]
    assert [item["fact_type"] for item in facts] == [
        "year_over_year_change",
        "percentage_of_total",
        "year_over_year_change",
        "percentage_of_total",
    ]
    assert [item["period_start"] for item in facts] == [
        "2026-04-01",
        "2026-04-01",
        "2026-01-01",
        "2026-01-01",
    ]


def test_wm_dividend_rates_periods_signs_and_run_rates_are_typed():
    payload = _wm_payload()
    facts = [item for event in payload["events"] for item in event["numeric_evidence"]]

    prior_dividend = next(item for item in facts if item["value"] == 669_000_000)
    rate_2025 = next(item for item in facts if item["value"] == 0.825)
    reduction = next(item for item in facts if item["raw_value"] == 0.6)
    headwind = next(item for item in facts if item["raw_value"] == 70)
    run_rate = next(item for item in facts if item["value"] == 123_000_000)

    assert (prior_dividend["period_start"], prior_dividend["period_end"]) == (
        "2025-01-01",
        "2025-06-30",
    )
    assert (rate_2025["fact_type"], rate_2025["period_kind"], rate_2025["rate_basis"]) == (
        "quarterly_rate",
        "rate",
        "per_share_per_quarter",
    )
    assert (reduction["value"], reduction["direction"], reduction["impact"]) == (
        -0.006,
        "decrease",
        "adverse",
    )
    assert (headwind["value"], headwind["direction"], headwind["impact"]) == (
        -70.0,
        "decrease",
        "adverse",
    )
    assert (run_rate["fact_type"], run_rate["period_kind"]) == (
        "annualized_run_rate",
        "rate",
    )


def test_wm_real_source_records_pass_the_generic_semantic_audit():
    payload = _wm_payload()
    facts = [
        {
            **item,
            "fact_id": f"FACT-{index}",
            "metric_id": item["metric_name"],
            "mapping_status": item.get("mapping_status", "mapped"),
            "confidence": "high",
        }
        for index, event in enumerate(payload["events"], start=1)
        for item in event["numeric_evidence"]
    ]
    tables = [table for event in payload["events"] for table in event.get("table_contracts", [])]

    result = audit_semantic_records(facts=facts, tables=tables)

    assert result["status"] == "pass", result["errors"]


def test_wm_distinguishes_landfill_yield_from_collection_disposal_yield():
    payload = build_sec_operating_kpi_payload(
        ticker="WM",
        cik="823768",
        accession_number="0001104659-26-088016",
        filing_date="2026-07-29",
        primary_document="wm-20260630x10q.htm",
        html_documents=[
            """
            <p>We continue to see yield growth in our landfill business primarily
            driven by municipal solid waste, which achieved average yield of 5.2%
            and 5.9% for the three and six months ended June 30, 2026,
            respectively.</p>
            <p>Collection and Disposal yield was 3.6% for the three months ended
            June 30, 2026.</p>
            """
        ],
        retrieved_at="2026-08-02T12:00:00Z",
        report_date="2026-06-30",
        report_period_months=3,
    )
    names = [
        item["metric_name"]
        for event in payload["events"]
        for item in event["numeric_evidence"]
    ]

    assert any("landfill_average_yield" in name for name in names)
    assert any("collection_disposal_yield" in name for name in names)
    assert len(names) == len(set(names))
