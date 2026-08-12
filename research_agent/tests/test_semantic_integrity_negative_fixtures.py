"""Negative controls for the Room16 semantic-integrity contract.

Each deliberately broken record must be rejected with a stable machine-readable
error code.  The paired corrected record must pass the same validator.  These
fixtures are issuer-neutral on purpose: they describe error classes, not WM
claim IDs or individual SEC documents.
"""

from copy import deepcopy

import pytest

from research_agent.quality.semantic_contracts import audit_semantic_records


BASE_FACT = {
    "fact_id": "FACT-001",
    "metric_id": "revenue_usd",
    "fact_type": "period_total",
    "raw_text": "$100 million",
    "normalized_magnitude": 100_000_000.0,
    "signed_value": 100_000_000.0,
    "direction": "neutral",
    "impact": "neutral",
    "unit": "currency",
    "currency": "USD",
    "period_kind": "duration",
    "period_start": "2026-01-01",
    "period_end": "2026-06-30",
    "comparison_period_start": None,
    "comparison_period_end": None,
    "rate_basis": None,
    "is_zero": False,
    "is_not_applicable": False,
    "is_missing": False,
    "mapping_status": "mapped",
    "confidence": "high",
    "evidence_id": "EVIDENCE-001",
    "source_id": "SOURCE-001",
    "source_locator": "table-1:r1:c1",
}


def _fact(**updates):
    value = deepcopy(BASE_FACT)
    value.update(updates)
    return value


def _error_codes(*, facts=(), tables=(), claims=(), sources=()):
    return {
        item["error"]
        for item in audit_semantic_records(
            facts=list(facts),
            tables=list(tables),
            claims=list(claims),
            sources=list(sources),
        )["errors"]
    }


@pytest.mark.parametrize(
    ("error", "broken", "corrected"),
    [
        (
            "table_comparison_semantics_invalid",
            {
                "tables": [{
                    "table_id": "TABLE-YIELD",
                    "table_semantic_type": "period_measure_comparison",
                    "period_axis": ["3M 2026", "6M 2026"],
                    "metric_axis": ["change_usd", "share_of_total_pct"],
                    "column_headers": ["3M 2026", "3M 2025", "6M 2026", "6M 2025"],
                    "cells": [],
                }],
            },
            {
                "tables": [{
                    "table_id": "TABLE-YIELD",
                    "source_id": "SOURCE-001",
                    "source_locator": "table-1",
                    "title": "Total average yield",
                    "subtitle": None,
                    "header_rows": [["", "Three Months Ended", "Six Months Ended"], ["", "Amount", "% of total", "Amount", "% of total"]],
                    "row_headers": ["Total average yield"],
                    "column_headers": ["3M 2026 change_usd", "3M 2026 share_of_total_pct", "6M 2026 change_usd", "6M 2026 share_of_total_pct"],
                    "row_dimension": "metric",
                    "column_dimension": "period_x_measure",
                    "period_axis": ["3M 2026", "6M 2026"],
                    "metric_axis": ["change_usd", "share_of_total_pct"],
                    "unit_axis": ["currency", "percent", "currency", "percent"],
                    "currency_axis": ["USD", None, "USD", None],
                    "comparison_axis": ["3M 2025", None, "6M 2025", None],
                    "value_role": ["year_over_year_change", "percentage_of_total", "year_over_year_change", "percentage_of_total"],
                    "table_semantic_type": "period_measure_comparison",
                    "cells": [],
                }],
            },
        ),
        (
            "comparison_period_mismatch",
            {"facts": [_fact(fact_type="period_total", metric_id="dividends_paid_usd_prior", period_start="2026-01-01", period_end="2026-06-30", comparison_period_start="2025-01-01", comparison_period_end="2025-06-30")]},
            {"facts": [_fact(fact_type="period_total", metric_id="dividends_paid_usd_prior", period_start="2025-01-01", period_end="2025-06-30", comparison_period_start=None, comparison_period_end=None)]},
        ),
        (
            "rate_period_kind_mismatch",
            {"facts": [_fact(metric_id="quarterly_dividend_per_share_usd", fact_type="period_total", rate_basis="per_share_per_quarter")]},
            {"facts": [_fact(metric_id="quarterly_dividend_per_share_usd", fact_type="quarterly_rate", period_kind="rate", rate_basis="per_share_per_quarter")]},
        ),
        (
            "direction_sign_mismatch",
            {"facts": [_fact(metric_id="revenue_guidance_change_pct", fact_type="guidance_change", raw_text="reduced by approximately 0.6%", normalized_magnitude=0.006, signed_value=0.006, direction="decrease", impact="adverse", unit="percent", currency=None, period_kind="guidance")]},
            {"facts": [_fact(metric_id="revenue_guidance_change_pct", fact_type="guidance_change", raw_text="reduced by approximately 0.6%", normalized_magnitude=0.006, signed_value=-0.006, direction="decrease", impact="adverse", unit="percent", currency=None, period_kind="guidance")]},
        ),
        (
            "impact_direction_missing",
            {"facts": [_fact(metric_id="wildfire_cleanup_headwind_bps", fact_type="contribution_to_change", raw_text="70-basis point headwind", normalized_magnitude=70.0, signed_value=70.0, direction="neutral", impact="neutral", unit="basis_points", currency=None)]},
            {"facts": [_fact(metric_id="wildfire_cleanup_headwind_bps", fact_type="contribution_to_change", raw_text="70-basis point headwind", normalized_magnitude=70.0, signed_value=-70.0, direction="decrease", impact="adverse", unit="basis_points", currency=None)]},
        ),
        (
            "not_applicable_zero_collision",
            {"facts": [_fact(metric_id="integration_costs_collection", fact_type="reconciliation_component", raw_text="—", normalized_magnitude=0.0, signed_value=0.0, is_zero=True, is_not_applicable=True, unit=None, currency=None)]},
            {"facts": [_fact(metric_id="integration_costs_collection", fact_type="reconciliation_component", raw_text="—", normalized_magnitude=None, signed_value=None, is_zero=False, is_not_applicable=True, unit=None, currency=None)]},
        ),
        (
            "claim_numeric_coverage_incomplete",
            {"claims": [{"claim_id": "CLAIM-001", "report_span": "$10, $20, 30% and 40%", "numeric_mentions": ["$10", "$20", "30%", "40%"], "numeric_bindings": [{"fact_id": "F1", "evidence_id": "E1"}, {"fact_id": "F2", "evidence_id": "E2"}], "render_disposition": "included_main_report", "source_ids": ["SOURCE-001"]}]},
            {"claims": [{"claim_id": "CLAIM-001", "report_span": "$10, $20, 30% and 40%", "numeric_mentions": ["$10", "$20", "30%", "40%"], "numeric_bindings": [{"fact_id": f"F{i}", "evidence_id": f"E{i}"} for i in range(1, 5)], "render_disposition": "included_main_report", "source_ids": ["SOURCE-001"]}]},
        ),
        (
            "source_disposition_claim_mismatch",
            {"claims": [{"claim_id": "CLAIM-001", "report_span": "Appendix fact", "numeric_mentions": [], "numeric_bindings": [], "render_disposition": "included_appendix", "source_ids": ["SOURCE-001"]}], "sources": [{"source_id": "SOURCE-001", "report_disposition": "included_main_report"}]},
            {"claims": [{"claim_id": "CLAIM-001", "report_span": "Appendix fact", "numeric_mentions": [], "numeric_bindings": [], "render_disposition": "included_appendix", "source_ids": ["SOURCE-001"]}], "sources": [{"source_id": "SOURCE-001", "report_disposition": "included_appendix"}]},
        ),
        (
            "metric_period_role_mismatch",
            {"facts": [_fact(metric_id="free_cash_flow_guidance_range", fact_type="guidance_range", period_kind="trailing_twelve_months")]},
            {"facts": [_fact(metric_id="free_cash_flow_guidance_range", fact_type="guidance_range", period_kind="guidance")]},
        ),
        (
            "unresolved_metric_promoted",
            {"facts": [_fact(metric_id="event_12_value_01", mapping_status="unresolved", confidence="high")]},
            {"facts": [_fact(metric_id="collection_disposal_yield_pct", mapping_status="mapped", confidence="high", fact_type="year_over_year_change", unit="percent", currency=None, period_kind="comparison", comparison_period_start="2025-01-01", comparison_period_end="2025-06-30")]},
        ),
    ],
)
def test_semantic_integrity_negative_fixture(error, broken, corrected):
    broken_codes = _error_codes(**broken)
    corrected_codes = _error_codes(**corrected)

    assert error in broken_codes
    assert error not in corrected_codes

