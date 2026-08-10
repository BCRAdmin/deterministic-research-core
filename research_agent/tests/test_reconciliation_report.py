from research_agent.reconciliation.canonical_financials import CanonicalFinancials, CanonicalMetric
from research_agent.reconciliation.reconciliation_report import (
    deduplicate_reconciliation_warnings,
    render_current_period_reconciliation_summary,
    render_reconciliation_report,
    save_current_period_reconciliation_summary,
    save_reconciliation_report,
    save_reconciliation_warnings,
)
from research_agent.research_core.models.metrics_packet import FundamentalMetrics, MetricsPacket, TechnicalMetrics, ValuationMetrics


def test_deduplicates_only_exact_reconciliation_warnings_in_source_order():
    first = {
        "severity": "warning",
        "code": "MISSING_COMPATIBLE_NUMERATOR",
        "metric": "ebitda",
        "message": "EBITDA is unavailable.",
    }
    distinct_same_code = {
        **first,
        "metric": "gross_profit",
        "message": "Gross profit is unavailable.",
    }

    assert deduplicate_reconciliation_warnings(
        [first, distinct_same_code, dict(first)]
    ) == [first, distinct_same_code]


def test_reconciliation_report_is_generated(tmp_path):
    canonical = CanonicalFinancials(
        ticker="MDB",
        as_of_date="2026-05-01",
        metrics=[
            CanonicalMetric(
                metric_name="revenue",
                value=2_460_000_000,
                unit="usd",
                period="FY2026",
                basis="gaap",
                statement_type="income_statement",
                source_ids=["SEC"],
                evidence_ids=["MDB_SEC_REVENUE"],
                confidence="high",
            )
        ],
    )
    warnings = [{"severity": "warning", "code": "TRUE_SOURCE_VALUE_DISAGREEMENT", "message": "Example warning."}]

    markdown = render_reconciliation_report(canonical, warnings)
    report_path = save_reconciliation_report(markdown, tmp_path / "reconciliation_report.md")
    warnings_path = save_reconciliation_warnings(warnings, tmp_path / "reconciliation_warnings.json")

    assert report_path.exists()
    assert warnings_path.exists()
    assert "# Reconciliation Report - MDB" in markdown
    assert "TRUE_SOURCE_VALUE_DISAGREEMENT" in markdown


def test_current_period_reconciliation_summary_is_short_and_current(tmp_path):
    canonical = CanonicalFinancials(
        ticker="MDB",
        as_of_date="2026-05-01",
        metrics=[
            CanonicalMetric(
                metric_name="revenue",
                value=2_460_000_000,
                unit="usd",
                period="FY2026",
                period_bucket="annual",
                basis="gaap",
                statement_type="income_statement",
                source_ids=["SEC"],
                evidence_ids=["MDB_SEC_REVENUE"],
                confidence="high",
            )
        ],
    )
    metrics = MetricsPacket(
        ticker="MDB",
        as_of_date="2026-05-01",
        technical=TechnicalMetrics(indicator_date="2026-04-30", close=250),
        fundamentals=FundamentalMetrics(fiscal_period="FY2026", revenue_ttm=2_460_000_000),
        valuation=ValuationMetrics(ev_to_sales=10),
    )

    markdown = render_current_period_reconciliation_summary(canonical, metrics, [])
    path = save_current_period_reconciliation_summary(markdown, tmp_path / "current_period_reconciliation_summary.md")

    assert path.exists()
    assert "# Current Period Reconciliation Summary - MDB" in markdown
    assert "Final Metrics Used" in markdown
    assert "revenue_ttm" in markdown
