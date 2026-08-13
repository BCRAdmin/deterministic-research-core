"""Issuer-neutral semantic audit contracts.

The module is intentionally the single gate used by extraction fixtures,
authority artifacts and the final release invariant report.
"""

from __future__ import annotations

import re
from typing import Any, Iterable, Mapping


FACT_TYPES = {
    "instant_value",
    "period_total",
    "quarterly_rate",
    "annual_rate",
    "annualized_run_rate",
    "year_over_year_change",
    "sequential_change",
    "basis_point_change",
    "guidance_range",
    "guidance_change",
    "contribution_to_change",
    "percentage_of_total",
    "reconciliation_component",
    "per_share_rate",
    "stock_value",
    "flow_value",
    "balance_value",
}

RATE_FACT_TYPES = {"quarterly_rate", "annual_rate", "annualized_run_rate", "per_share_rate"}
CHANGE_FACT_TYPES = {
    "year_over_year_change",
    "sequential_change",
    "basis_point_change",
    "guidance_change",
    "contribution_to_change",
}
FACT_TYPE_PERIOD_KINDS = {
    "instant_value": {"instant"},
    "balance_value": {"instant"},
    "stock_value": {"instant"},
    "period_total": {"duration", "trailing_twelve_months"},
    "flow_value": {"duration", "trailing_twelve_months"},
    "reconciliation_component": {"duration", "comparison"},
    "year_over_year_change": {"comparison"},
    "sequential_change": {"comparison"},
    "basis_point_change": {"comparison"},
    "contribution_to_change": {"comparison"},
    "percentage_of_total": {"duration", "trailing_twelve_months", "instant"},
    "guidance_range": {"guidance"},
    "guidance_change": {"guidance", "comparison"},
    "quarterly_rate": {"rate"},
    "annual_rate": {"rate"},
    "annualized_run_rate": {"rate"},
    "per_share_rate": {"rate"},
}
POSITIONAL_METRIC_RE = re.compile(r"(?:^|_)(?:event|value)_?\d+(?:_|$)", re.IGNORECASE)
ADVERSE_WORD_RE = re.compile(
    r"\b(?:reduced?|lowered|decreas(?:e|ed)|declin(?:e|ed)|headwind|adverse|fell)\b",
    re.IGNORECASE,
)


def audit_semantic_records(
    *,
    facts: Iterable[Mapping[str, Any]] = (),
    tables: Iterable[Mapping[str, Any]] = (),
    claims: Iterable[Mapping[str, Any]] = (),
    sources: Iterable[Mapping[str, Any]] = (),
) -> dict[str, Any]:
    """Audit structured records without using text proximity as identity.

    Every error includes the exact record IDs involved.  Prose is consulted
    only for contradiction detection (for example ``headwind`` paired with a
    positive impact); identity comes from metric, fact, evidence and source
    IDs.
    """

    fact_list = [dict(item) for item in facts]
    table_list = [dict(item) for item in tables]
    claim_list = [dict(item) for item in claims]
    source_list = [dict(item) for item in sources]
    errors: list[dict[str, Any]] = []

    def fail(code: str, *, record_id: str | None, detail: str) -> None:
        errors.append({"error": code, "record_id": record_id, "detail": detail})

    for table in table_list:
        table_id = str(table.get("table_id") or "") or None
        if not _table_contract_complete(table):
            fail(
                "table_headers_not_preserved",
                record_id=table_id,
                detail="The canonical table contract is incomplete.",
            )
        if table.get("table_semantic_type") == "period_measure_comparison" and not _period_measure_axis_valid(table):
            fail(
                "table_comparison_semantics_invalid",
                record_id=table_id,
                detail="Period and measure axes are flattened or misaligned.",
            )
        if not _table_cells_aligned(table):
            fail(
                "table_cell_alignment_invalid",
                record_id=table_id,
                detail="A cell is missing its row/column identity or references an unknown table.",
            )

    for fact in fact_list:
        fact_id = str(fact.get("fact_id") or fact.get("claim_id") or fact.get("metric_id") or fact.get("metric") or "") or None
        metric_id = str(fact.get("metric_id") or fact.get("metric") or "")
        fact_type = str(fact.get("fact_type") or "")
        period_kind = str(fact.get("period_kind") or "")
        rate_basis = fact.get("rate_basis")
        direction = str(fact.get("direction") or "neutral")
        impact = str(fact.get("impact") or "neutral")
        signed_value = fact.get("signed_value", fact.get("value"))
        raw_text = str(fact.get("raw_text") or "")

        if fact_type and fact_type not in FACT_TYPES:
            fail("fact_type_invalid", record_id=fact_id, detail=f"Unknown fact_type={fact_type}.")
        allowed_period_kinds = FACT_TYPE_PERIOD_KINDS.get(fact_type)
        if allowed_period_kinds is not None and period_kind not in allowed_period_kinds:
            fail(
                "fact_type_period_kind_mismatch",
                record_id=fact_id,
                detail=(
                    f"fact_type={fact_type} requires period_kind in "
                    f"{sorted(allowed_period_kinds)}, found {period_kind}."
                ),
            )
        if rate_basis and (fact_type not in RATE_FACT_TYPES or period_kind not in {"rate", "guidance"}):
            fail(
                "rate_period_kind_mismatch",
                record_id=fact_id,
                detail=f"rate_basis={rate_basis} conflicts with fact_type={fact_type}, period_kind={period_kind}.",
            )
        if fact_type in RATE_FACT_TYPES and not rate_basis:
            fail("rate_basis_missing", record_id=fact_id, detail="A rate fact has no explicit rate_basis.")
        if fact_type == "guidance_range" and period_kind != "guidance":
            fail(
                "metric_period_role_mismatch",
                record_id=fact_id,
                detail="A guidance range is not typed as a guidance period.",
            )
        if fact_type == "annualized_run_rate" and period_kind != "rate":
            fail(
                "metric_period_role_mismatch",
                record_id=fact_id,
                detail="An annualized run rate is modeled as a historical period total.",
            )
        if fact_type == "period_total" and "prior" in metric_id and fact.get("comparison_period_start"):
            if fact.get("period_start") != fact.get("comparison_period_start") or fact.get("period_end") != fact.get("comparison_period_end"):
                fail(
                    "comparison_period_mismatch",
                    record_id=fact_id,
                    detail="A prior-period fact carries current-period dates.",
                )
        if fact_type in {"year_over_year_change", "percentage_of_total"} and fact_type == "year_over_year_change":
            if not fact.get("comparison_period_start") or not fact.get("comparison_period_end"):
                fail(
                    "comparison_period_missing",
                    record_id=fact_id,
                    detail="A year-over-year change has no explicit comparison window.",
                )
        if direction == "decrease" and signed_value is not None and float(signed_value) > 0:
            fail(
                "direction_sign_mismatch",
                record_id=fact_id,
                detail="direction=decrease requires a non-positive signed value.",
            )
        if direction == "increase" and signed_value is not None and float(signed_value) < 0:
            fail(
                "direction_sign_mismatch",
                record_id=fact_id,
                detail="direction=increase requires a non-negative signed value.",
            )
        if ADVERSE_WORD_RE.search(raw_text) and (direction not in {"decrease", "negative"} or impact != "adverse"):
            code = "impact_direction_missing" if "headwind" in raw_text.casefold() else "direction_sign_mismatch"
            fail(code, record_id=fact_id, detail="Adverse source language is not encoded in direction and impact.")
        if fact.get("is_not_applicable") and (
            fact.get("is_zero")
            or fact.get("normalized_magnitude") is not None
            or fact.get("signed_value") is not None
            or fact.get("value") is not None
        ):
            fail(
                "not_applicable_zero_collision",
                record_id=fact_id,
                detail="Not-applicable cells must not contain a numeric zero or value.",
            )
        unresolved = str(fact.get("mapping_status") or "mapped") != "mapped" or bool(POSITIONAL_METRIC_RE.search(metric_id))
        if unresolved and str(fact.get("confidence") or "high") == "high":
            fail(
                "unresolved_metric_promoted",
                record_id=fact_id,
                detail=f"Unresolved metric {metric_id!r} was promoted at high confidence.",
            )

    for claim in claim_list:
        claim_id = str(claim.get("claim_id") or "") or None
        mentions = list(claim.get("numeric_mentions") or [])
        bindings = list(claim.get("numeric_bindings") or [])
        complete_bindings = [
            item for item in bindings
            if item.get("fact_id") and item.get("evidence_id")
        ]
        if len(complete_bindings) != len(mentions):
            fail(
                "claim_numeric_coverage_incomplete",
                record_id=claim_id,
                detail=f"numeric_mentions={len(mentions)} complete_bindings={len(complete_bindings)}.",
            )

    source_claims: dict[str, list[Mapping[str, Any]]] = {}
    for claim in claim_list:
        for source_id in claim.get("source_ids") or []:
            source_claims.setdefault(str(source_id), []).append(claim)
    for source in source_list:
        source_id = str(source.get("source_id") or "")
        dispositions = {
            str(claim.get("render_disposition") or "")
            for claim in source_claims.get(source_id, [])
        }
        declared = str(source.get("report_disposition") or "")
        expected = _aggregate_source_disposition(dispositions)
        if expected and declared != expected:
            fail(
                "source_disposition_claim_mismatch",
                record_id=source_id or None,
                detail=f"declared={declared or 'missing'} expected={expected} from claim render states.",
            )

    return {
        "contract_id": "room16.semantic_record_audit",
        "contract_version": 1,
        "status": "pass" if not errors else "fail",
        "errors": errors,
        "error_codes": sorted({item["error"] for item in errors}),
        "counts": {
            "facts": len(fact_list),
            "tables": len(table_list),
            "claims": len(claim_list),
            "sources": len(source_list),
            "errors": len(errors),
        },
    }


def _table_contract_complete(table: Mapping[str, Any]) -> bool:
    required = (
        "table_id",
        "source_id",
        "source_locator",
        "header_rows",
        "row_headers",
        "column_headers",
        "row_dimension",
        "column_dimension",
        "period_axis",
        "metric_axis",
        "unit_axis",
        "currency_axis",
        "comparison_axis",
        "value_role",
        "table_semantic_type",
    )
    return all(key in table and table.get(key) is not None for key in required)


def _period_measure_axis_valid(table: Mapping[str, Any]) -> bool:
    periods = [str(item) for item in table.get("period_axis") or []]
    metrics = [str(item) for item in table.get("metric_axis") or []]
    headers = [str(item) for item in table.get("column_headers") or []]
    if not periods or not metrics or len(headers) != len(periods) * len(metrics):
        return False
    return all(
        any(period in header for period in periods)
        and any(metric in header for metric in metrics)
        for header in headers
    )


def _table_cells_aligned(table: Mapping[str, Any]) -> bool:
    table_id = table.get("table_id")
    for cell in table.get("cells") or []:
        if cell.get("table_id") != table_id or not cell.get("cell_id") or not cell.get("row_key") or not cell.get("column_key"):
            return False
        if cell.get("is_not_applicable") and (
            cell.get("is_zero") or cell.get("normalized_value") is not None
        ):
            return False
    return True


def _aggregate_source_disposition(dispositions: set[str]) -> str | None:
    values = {item for item in dispositions if item}
    if not values:
        return None
    if "included_main_report" in values:
        return "included_main_report"
    if "included_appendix" in values:
        return "included_appendix"
    if "superseded" in values:
        return "superseded"
    if "excluded_outside_scope" in values:
        return "excluded_outside_scope"
    if "excluded_immaterial" in values:
        return "excluded_immaterial"
    return sorted(values)[0]
