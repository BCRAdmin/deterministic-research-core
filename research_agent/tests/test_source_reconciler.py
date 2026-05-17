from research_agent.reconciliation.canonical_financials import CanonicalMetric
from research_agent.reconciliation.source_reconciler import (
    build_canonical_financials_from_facts,
    canonical_financials_to_fundamentals,
    reconcile_metric,
)
from research_agent.sources.sec.companyfacts_parser import ParsedFact


def _metric(value, basis, source_id="SEC", confidence="high", metric_name="eps"):
    return CanonicalMetric(
        metric_name=metric_name,
        value=value,
        unit="usd_per_share",
        period="FY2027",
        fiscal_year=2027,
        fiscal_period="FY",
        period_bucket="annual",
        start_date="2026-02-01",
        end_date="2027-01-31",
        basis=basis,
        statement_type="guidance" if "guidance" in metric_name else "income_statement",
        source_ids=[source_id],
        evidence_ids=[source_id],
        confidence=confidence,
    )


def _fact(metric_name, value, fp, start, end, accession):
    return ParsedFact(
        metric_name=metric_name,
        value=value,
        unit="USD",
        period=f"FY2026_{fp}",
        fy=2026,
        fp=fp,
        form="10-K" if fp == "FY" else "10-Q",
        filed="2026-03-01",
        start=start,
        end=end,
        accession=accession,
    )


def test_gaap_and_non_gaap_metrics_are_not_merged():
    canonical, warnings = reconcile_metric("eps", [
        _metric(value=0.18, basis="gaap"),
        _metric(value=5.93, basis="non_gaap", source_id="IR"),
    ])

    bases = {metric.basis for metric in canonical}

    assert "gaap" in bases
    assert "non_gaap" in bases


def test_guidance_and_consensus_remain_separate():
    canonical, warnings = reconcile_metric("forward_eps", [
        _metric(value=5.93, basis="company_defined", source_id="IR", metric_name="company_guidance_eps"),
        _metric(value=7.05, basis="consensus", source_id="PROVIDER", metric_name="consensus_forward_eps"),
    ])

    bases = {metric.basis for metric in canonical}

    assert "company_defined" in bases
    assert "consensus" in bases


def test_source_value_disagreement_warns_within_same_basis():
    canonical, warnings = reconcile_metric("revenue", [
        _metric(value=100, basis="gaap", source_id="SEC", metric_name="revenue"),
        _metric(value=105, basis="gaap", source_id="VENDOR", metric_name="revenue"),
    ])

    assert any(warning["code"] == "TRUE_SOURCE_VALUE_DISAGREEMENT" for warning in warnings)
    assert canonical[0].value == 100


def test_period_type_variants_are_ignored_not_warned():
    canonical, warnings = reconcile_metric("revenue", [
        _metric(value=100, basis="gaap", source_id="SEC", metric_name="revenue"),
        _metric(value=25, basis="gaap", source_id="SEC", metric_name="revenue").model_copy(
            update={
                "period": "Q4_FY2027_quarterly",
                "fiscal_period": "FY",
                "period_bucket": "quarterly",
                "start_date": "2026-11-01",
                "end_date": "2027-01-31",
            }
        ),
    ])

    assert not any(warning["code"] == "TRUE_SOURCE_VALUE_DISAGREEMENT" for warning in warnings)
    assert any(warning["code"] == "PERIOD_TYPE_MISMATCH_IGNORED" for warning in warnings)


def test_ytd_source_disagreements_are_ignored_not_true_warnings():
    ytd_metric = _metric(value=300, basis="gaap", source_id="SEC", metric_name="revenue").model_copy(
        update={
            "period": "Q2_FY2027_ytd",
            "fiscal_period": "Q2",
            "period_bucket": "ytd",
            "start_date": "2026-02-01",
            "end_date": "2026-07-31",
        }
    )

    canonical, warnings = reconcile_metric("revenue", [
        ytd_metric,
        ytd_metric.model_copy(update={"value": 305, "source_ids": ["SEC_RESTATEMENT"]}),
    ])

    assert not any(warning["code"] == "TRUE_SOURCE_VALUE_DISAGREEMENT" for warning in warnings)
    assert any(warning["code"] == "PERIOD_TYPE_MISMATCH_IGNORED" for warning in warnings)
    assert canonical[0].value == 300


def test_canonical_financials_can_be_built_from_sec_facts():
    facts = [
        _fact("revenue", 10, "Q1", "2025-02-01", "2025-04-30", "q1"),
        _fact("revenue", 11, "Q2", "2025-05-01", "2025-07-31", "q2"),
        _fact("revenue", 12, "Q3", "2025-08-01", "2025-10-31", "q3"),
        _fact("revenue", 13, "Q4", "2025-11-01", "2026-01-31", "q4"),
    ]

    canonical, warnings = build_canonical_financials_from_facts("TEST", "2026-05-01", facts)
    fundamentals = canonical_financials_to_fundamentals(canonical)

    assert canonical.get_metric("revenue", "Q4_FY2026_quarterly").value == 13
    assert fundamentals["quarterly"]["revenue"] == [10, 11, 12, 13]
